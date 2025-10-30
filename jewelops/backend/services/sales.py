from decimal import Decimal
from django.db import IntegrityError, transaction
from accounting_ledger.models import RST, PaymentMethod, RSTItem, Sales, Item, SaleItem, SalePayment, GoldPayment, ItemStatus, PaymentKind
from accounting_ledger.utils import parse_item_codes, parse_payment_methods

def create_sales_from_row(row, *, item_status):
    sales_row_created=[]
    sale = Sales.objects.create(
        business_date=row.get('business_date'),
        customer_name=row.get('customer_name', ''),
        sold_by=row.get('sold_by', ''),
        invoice_number=row.get('invoice_number'),
        item_count=row.get('item_count', 0),
        total_weight=row.get('gold_weight', Decimal('0')),
        total_sale_price=row.get('sale_price')
    )
    sale.save()
    print("row sale price",row.get('sale_price'))
    if (row.get("sale_price")).strip().lower() == 'rst':
        rst = RST.objects.create(
                sale=Sales.objects.get(id=sale.id),
                #TODO:
                #rst db needs to be fixed, also do we want rstItem table?
                rst_adv=row.get('rst_booking_payment') 
        )
        rst.save()

    # Create items
    item_codes, item_names = parse_item_codes(row.get('item_code'), row.get('item'))
    for idx, code in enumerate(item_codes):
        name = item_names[idx] if idx < len(item_names) else ''
        defaults = {
            'purity': row.get('kdm_vori'),
            'description': name,
            'status': item_status
        }
        try:
            item, created = Item.objects.get_or_create(code=code, defaults=defaults)
        except IntegrityError:
            item = Item.objects.get(code=code)
            created = False
        if not created:
            item.status = item_status
            item.save(update_fields=['status'])
    
        sale_item = SaleItem.objects.create(
            sale=Sales.objects.get(id=sale.id),
            item=Item.objects.get(code=code),
            purity_price=row.get('kdm_vori'),
            description=name
        )
        sale_item.save()

        if (row.get("sale_price")).strip().lower() == 'rst':
            rst_item = RSTItem.objects.create(
                rst=RST.objects.get(id=rst.id),
                item=Item.objects.get(code=code),
            )
            rst_item.save()


    #parse the payment type
    pay_types = parse_payment_methods(row.get('payment_type', ''))
    if not pay_types:
        pay_types = PaymentMethod.CASH
    for pay_type in pay_types:
        payment = SalePayment.objects.create(
            sale=Sales.objects.get(id=sale.id),
            #TODO: Support accurate payment methods
            method=PaymentMethod.CASH,
            amount=row.get('cash_card_payment'),
            due_amount=row.get('due_amount', 0),
            due_by=row.get('due_by', ''),
            description=pay_type,
            kind=PaymentKind.PAYMENT
        )
        payment.save()

        has_gold_payment = row.get('gold_payment', '')
        if has_gold_payment != '' and payment.description.lower() == 'gold':
            gold_payment = GoldPayment.objects.create(
                payment=SalePayment.objects.get(id=payment.id),
                weight=row.get('gold_payment'),
                #TODO: Business Logic doesn't support the exact purity
                purity='Not Specified'
            )
            gold_payment.save()
    sales_row_created.append(sale)
    return sales_row_created


