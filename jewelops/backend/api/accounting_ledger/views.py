from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal, InvalidOperation
from django.db import transaction
from api.accounting_ledger.serializers import SalesComposeSerializer


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

        #create item if it does not exist

        #iterate through each row in the request data
        #check if the request data has orders
            # if Order exists in sale (sale_price = order)
                # create a sale_payload and call database?
                # cause order table has a sales foreign key
                # call the Order serializer to validate and create order sale details
            #create

        for idx, row in enumerate(rows):
            def to_decimal(v, default='0'):
                try:
                    return Decimal(str(v))
                except (InvalidOperation, TypeError):
                    return Decimal(default)
                
            cleaned_row = {
                'business_date': business_date,
                'invoice_number': int(row.get('invoice_number')) or None,
                'customer_name': row.get('customer') or row.get('customer_name') or '',
                'sold_by': row.get('sold_by') or '',
                'item_count': int(row.get('quantity') or 0),
                'gold_weight': to_decimal(row.get('gold_weight'), '0'),
                'sale_price': row.get('sale_price') or '',
                'item_code': row.get('item_code') or '',    # parser will handle formats like "(123)(456)"
                'item': row.get('item') or '',              # names like "Earring,Wristlet"
                'kdm_vori': row.get('kdm_vori') or '',
                'gold_payment': row.get('gold_payment') or '',
                'cash_card_payment': int(row.get('cash_card_payment') or 0),
                'customer_due': to_decimal(row.get('customer_due'), '0'),
                'due_by': row.get('due_by') or '',
                'payment_type': row.get('payment_type') or '',
            }
            #Map incoming row into SalesComposeSerializer expected format
            sale_payload = {
                'items': [cleaned_row],
            }
            serializer = SalesComposeSerializer(data=sale_payload)
            try:
                with transaction.atomic():
                    if serializer.is_valid(raise_exception=True):
                        sale_instance = serializer.save()
                        results.append({'row': idx,'sale_id': sale_instance.id, 'invoice_number': sale_instance.invoice_number})
            except Exception as e:
                print(f"Error processing row {idx}: {str(e)}")
                errors.append({
                    'row': idx,
                    'errors': str(e),
                })
        # Return success response
        return Response({
            "message": "Sales data received successfully!",
            "received_data": request.data,
            "user": str(request.user),
            "results": results,
            "errors": errors,
        }, status=status.HTTP_200_OK)