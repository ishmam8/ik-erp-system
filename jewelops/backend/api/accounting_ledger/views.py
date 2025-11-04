from datetime import date
from django.db import transaction
from django.db.models import Prefetch
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny

from api.accounting_ledger.serializers import OrderComposeSerializer, RSTBookingSerializer, SalesComposeSerializer, SalesListSerializer
from accounting_ledger.utils import to_decimal

import logging

from accounting_ledger.models import SaleItem, Sales
logger = logging.getLogger("ledger.sales")


class SalesView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # Print request data to console
        print("=" * 50)
        print("SALES REQUEST RECEIVED")
        print(f"User: {request.user}")
        print(f"Data: {request.data}")
        print(f"Headers: {request.headers}")
        print("=" * 50)
        
        rows = request.data.get("sales") or []
        order_rows = request.data.get("orders") or []
        business_date = request.data.get("date")
        order_dict = {}
        for o in order_rows:
            inv = o.get("invoice_number")
            if inv is not None and inv != "":
                order_dict[str(inv)] = o  # normalize key to string
        results = []
        errors = []
        serializer = None

        logger.info(
            "Create user_id=%s date=%s sales_count=%s orders_count=%s invoice_numbers=%s",
            getattr(request.user, "id", None),
            request.data.get("date"),
            len(rows),
            len(order_rows),
            [r.get("invoice_number") for r in rows],
        )
        
        for idx, row in enumerate(rows):
            inv_num = int(row.get('invoice_number')) or None
            matching_order = order_dict.get(str(inv_num))
            order_delivery_date = matching_order.get("estimated_order_delivery_date") if matching_order else None
            order_completed_date = matching_order.get("order_completed_date") if matching_order else None
            delivery_date = None if not order_delivery_date else order_delivery_date
            completed_at = None if not order_completed_date else order_completed_date

            cleaned_row = {
                'business_date': business_date,
                'invoice_number': inv_num,
                'customer_name': row.get('customer') or row.get('customer_name') or '',
                
                'item_code': row.get('item_code') or '',    # parser will handle formats like "(123)(456)"
                'item': row.get('item') or '', # names like "Earring,Wristlet"
                'item_count': int(row.get('quantity') or 0),
                'gold_weight': to_decimal(row.get('gold_weight'), '0'),
                'kdm_vori': row.get('kdm_vori') or '',

                'gold_payment': row.get('gold_payment') or '',
                'sale_price': row.get('sale_price') or '',
                'cash_card_payment': int(row.get('cash_card_payment') or 0),
                'payment_type': row.get('payment_type') or '',
                
                'sold_by': row.get('sold_by') or '',
                'due_amount': to_decimal(row.get('customer_due'), '0'),
                'due_by': row.get('due_by') or '',

                'rst_order': row.get('rst_order'), # is it rst/order/sale
                'rst_booking_payment': to_decimal(row.get('rst_payment'), '0'), # Only for RST bookings, final payment estimated #TODO:
                'rst_adv': to_decimal(row.get('rst_advanced'), '0'),       # Only for RST bookings, advance payment made
                'rst_status': row.get('rst_status') or '', #TODO: not using it for now

                'assigned_to': (matching_order.get("artisan") if matching_order else None),
                'is_completed': False, #TODO: change to a status
                'delivery_date': delivery_date,
                'completed_at': row.get('order_completed_date') or None, #TODO: need to figure this out 
                'order_description': (matching_order.get("item_name") if matching_order else None),
            }

            tag = (row.get("rst_order") or "")
            if tag == "RST":
                serializer = RSTBookingSerializer(data={"row": cleaned_row})
            elif tag == "ORDER":
                serializer = OrderComposeSerializer(data={"row": cleaned_row})
            else:
                serializer = SalesComposeSerializer(data={"row": cleaned_row})
            
            try:
                # keep atomic here; remove nested atomic in create_sales_from_columns
                with transaction.atomic():
                    serializer.is_valid(raise_exception=True)
                    sale_instance = serializer.save()
                    results.append({
                        "row": idx,
                        "sale_id": sale_instance.id,
                        "invoice_number": sale_instance.invoice_number
                    })
                    # logger.info(
                    #     "Row Saved",
                    #         "date": business_date,
                    #         "row_index": idx,
                    #         "invoice_number": sale_instance.invoice_number,
                    #         "sale_id": sale_instance.id,
                    # )
            except Exception as e:
                errors.append({"row": idx, "invoice_number": inv_num, "errors": str(e)})
                logger.warning(
                    "Row Failed date=%s invoice=%s error=%s data=%s",
                    business_date,
                    inv_num,
                    str(e),
                    cleaned_row,
                )

        logger.info(
            "Submission Report date=%s rows_attempted=%s rows_saved=%s rows_failed=%s saved_invoices=%s failed_invoices=%s",
            business_date,
            len(rows),
            len(results),
            len(errors),
            [r["invoice_number"] for r in results],
            [e["invoice_number"] for e in errors],
        )
        # Return success response
        return Response({
            "message": "Sales data received successfully!",
            "received_data": request.data,
            "user": str(request.user),
            "results": results,
            "errors": errors,
        }, status=status.HTTP_200_OK)
    

class SalesGetView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        month_str = request.query_params.get("month")
        include_items = request.query_params.get("include_items") == "true"

        # simple pagination guards
        try:
            limit = int(request.query_params.get("limit", 200))  # sane default
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response({"detail": "limit and offset must be integers"}, status=status.HTTP_400_BAD_REQUEST)

        if month_str:
            # expect "YYYY-MM"
            parts = month_str.split("-")
            if len(parts) != 2:
                return Response({"detail": "month must be in YYYY-MM format"}, status=status.HTTP_400_BAD_REQUEST)
            year, month = parts
            try:
                year = int(year)
                month = int(month)
            except ValueError:
                return Response({"detail": "month must be in YYYY-MM format"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # default to current month
            today = date.today()
            year = today.year
            month = today.month

        # base queryset
        qs = (
            Sales.objects
            .filter(business_date__year=year, business_date__month=month)
            .order_by("id")
        )

        # prefetch conditionally
        if include_items:
            qs = qs.prefetch_related(
                Prefetch(
                    "items",  # related_name on SaleItem.sale
                    queryset=SaleItem.objects.select_related("item")
                )
            )

        # also prefetch rst/order so serializer doesn't N+1
        qs = qs.select_related("rst_details", "order_details")

        # 4) apply pagination slice
        qs = qs[offset:offset + limit]

        serializer = SalesListSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)