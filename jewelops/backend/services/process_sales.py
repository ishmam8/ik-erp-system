from decimal import Decimal
from django.db import IntegrityError, transaction
from accounting_ledger.models import RST, PaymentMethod, RSTItem, Sales, Item, SaleItem, SalePayment, GoldPayment, ItemStatus, PaymentKind
from accounting_ledger.utils import parse_item_codes, parse_payment_methods, safe_int, to_decimal
import logging

from api.accounting_ledger.serializers import OrderComposeSerializer, RSTBookingSerializer, SalesComposeSerializer
logger = logging.getLogger("ledger.sales")



def process_sales_rows(rows, order_rows, business_date, user):
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
        getattr(user, "id", None),
        business_date,
        len(rows),
        len(order_rows),
        [r.get("invoice_number") for r in rows],
    )

    with transaction.atomic():
        for idx, row in enumerate(rows):
            inv_num = safe_int(row.get('invoice_number'))
            matching_order = order_dict.get(str(inv_num))
            order_delivery_date = matching_order.get("estimated_order_delivery_date") if matching_order else None
            order_completed_date = matching_order.get("order_completed_date") if matching_order else None
            delivery_date = None if not order_delivery_date else order_delivery_date
            completed_at = None if not order_completed_date else order_completed_date

            # print("MATCHING ORDER FOR INV", inv_num, row.get('item'),"IS", matching_order)
            print("RST ORDER:", row.get("rst_advanced"), " for INV:", inv_num)
            print("RST PARSED", to_decimal(row.get('rst_advanced'), '0'))
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
                'order_description': (matching_order.get("item_name") if matching_order else 'na'),
            }

            tag = (row.get("rst_order") or "")
            # 🔑 Only treat as ORDER if we actually have order meta for this invoice
            if tag == "ORDER" and matching_order is None:
                # This is likely a later "Advance" payment row, where customer is paying advance money, not the order header
                print(f"DEBUG: invoice {inv_num} tagged ORDER but no matching_order – treating as SALE")
                tag = ""   # force it to go through SalesComposeSerializer
            if tag == "RST":
                serializer = RSTBookingSerializer(data={"row": cleaned_row})
            elif tag == "ORDER":
                serializer = OrderComposeSerializer(data={"row": cleaned_row})
            else:
                serializer = SalesComposeSerializer(data={"row": cleaned_row})
            
            try:
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
    return results, errors


