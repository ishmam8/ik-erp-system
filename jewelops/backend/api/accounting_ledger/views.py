from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from api.accounting_ledger.serializers import OrderComposeSerializer, RSTBookingSerializer, SalesComposeSerializer
from accounting_ledger.utils import to_decimal


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

        rows = request.data.get("items") or []
        business_date = request.data.get("date")
        print(business_date)

        results = []
        errors = []
        serializer = None

        for idx, row in enumerate(rows):
            cleaned_row = {
                'business_date': business_date,
                'invoice_number': int(row.get('invoice_number')) or None,
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

                'is_rst': bool(row.get('is_rst')),
                'rst_booking_payment': to_decimal(row.get('rst_payment'), '0'), # Only for RST bookings, final payment estimated #TODO:
                'rst_adv': to_decimal(row.get('rst_advanced'), '0'),       # Only for RST bookings, advance payment made
                'rst_status': row.get('rst_status') or '',

                'assigned_to': row.get('order_assigned_to'),
                'is_completed': row.get('is_completed'),
                'delivery_date': row.get('order_delivery_date'),
                'completed_at': row.get('order_completed_date') or None ,
                'order_description': row.get('order_items') or '',
            }

            tag = (row.get("sale_price") or "").strip().lower()
            is_rst = bool(row.get("is_rst")) or tag == "rst"
            is_order = tag == "order"

            if is_rst:
                serializer = RSTBookingSerializer(data={"row": cleaned_row})
            elif is_order:
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
            except Exception as e:
                errors.append({"row": idx, "errors": str(e)})
        # Return success response
        return Response({
            "message": "Sales data received successfully!",
            "received_data": request.data,
            "user": str(request.user),
            "results": results,
            "errors": errors,
        }, status=status.HTTP_200_OK)