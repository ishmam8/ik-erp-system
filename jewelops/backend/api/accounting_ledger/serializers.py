from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from accounting_ledger.models import (
    Item, Sales, SaleItem, SalePayment, GoldPayment, RST, RSTItem, RSTVoided, 
    Order, Expense, PaymentMethod, PaymentKind, ExpenseCategory, ItemStatus, RSTStatus
)
from accounting_ledger.utils import parse_item_codes, parse_payment_methods


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = [
            'code', 'purity', 'weight', 'description', 'status', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SaleItemSerializer(serializers.ModelSerializer):
    # Include item details for read operations
    item_details = ItemSerializer(source='item', read_only=True)
    
    class Meta:
        model = SaleItem
        fields = [
            'id', 'sale', 'item', 'purity_price', 'item_details'
        ]


class SalePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalePayment
        fields = ['id', 'sale', 'method', 'amount', 'description', 'kind']


class GoldPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoldPayment
        fields = ['id', 'payment', 'weight', 'purity']


class RSTItemSerializer(serializers.ModelSerializer):
    # Include item details for read operations
    item_details = ItemSerializer(source='item', read_only=True)
    
    class Meta:
        model = RSTItem
        fields = ['id', 'rst', 'item', 'item_details']


class RSTVoidedSerializer(serializers.ModelSerializer):
    class Meta:
        model = RSTVoided
        fields = ['voided_at']


class RSTSerializer(serializers.ModelSerializer):
    rst_items = RSTItemSerializer(many=True, read_only=True)
    voided_info = RSTVoidedSerializer(read_only=True)
    number = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = RST
        fields = [
            'id', 'status', 'rst_adv', 'rst_due', 'rst_final_price', 
            'delivery_date', 'completed_at', 'number', 'rst_items', 'voided_info'
        ]


class RSTBookingSerializer(serializers.ModelSerializer):
    """Specialized serializer for creating RST bookings"""
    items = serializers.ListField(
        child=serializers.IntegerField(),  # List of item codes
        write_only=True
    )
    advance_payment = serializers.DecimalField(max_digits=10, decimal_places=2, write_only=True)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, write_only=True)
    
    # Sale fields
    business_date = serializers.DateField(write_only=True)
    customer_name = serializers.CharField(max_length=255, write_only=True)
    sold_by = serializers.CharField(max_length=100, write_only=True)
    
    class Meta:
        model = RST
        fields = [
            'id', 'rst_adv', 'rst_due', 'rst_final_price', 'delivery_date',
            'items', 'advance_payment', 'payment_method', 
            'business_date', 'customer_name', 'sold_by'
        ]
    
    def validate_items(self, value):
        """Validate that all items exist and are available"""
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        
        # Check if items exist and are available
        items = Item.objects.filter(code__in=value)
        if items.count() != len(value):
            missing = set(value) - set(items.values_list('code', flat=True))
            raise serializers.ValidationError(f"Items with codes {list(missing)} do not exist.")
        
        unavailable = items.exclude(status=ItemStatus.AVAILABLE)
        if unavailable.exists():
            codes = list(unavailable.values_list('code', flat=True))
            raise serializers.ValidationError(f"Items {codes} are not available for booking.")
        
        return value
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        advance_payment = validated_data.pop('advance_payment')
        payment_method = validated_data.pop('payment_method')
        
        # Sale data
        sale_data = {
            'business_date': validated_data.pop('business_date'),
            'customer_name': validated_data.pop('customer_name'),
            'sold_by': validated_data.pop('sold_by'),
            'invoice_number': Sales.objects.aggregate(
                max_invoice=Coalesce(models.Max('invoice_number'), 0)
            )['max_invoice'] + 1
        }
        
        with transaction.atomic():
            # Create sale
            sale = Sales.objects.create(**sale_data)
            
            # Create RST
            rst = RST.objects.create(
                sale=sale,
                status=RSTStatus.BOOKED,
                rst_adv=advance_payment,
                **validated_data
            )
            
            # Create RST items and update item status
            for item_code in items_data:
                item = Item.objects.get(code=item_code)
                RSTItem.objects.create(rst=rst, item=item)
                item.status = ItemStatus.RST_BOOKED
                item.save()
            
            # Create advance payment
            SalePayment.objects.create(
                sale=sale,
                method=payment_method,
                amount=advance_payment,
                kind=PaymentKind.RST_ADVANCE
            )
            
            # Update sale aggregates
            rst_items = Item.objects.filter(rstitem__rst=rst)
            sale.item_count = rst_items.count()
            sale.total_weight = rst_items.aggregate(
                total=Coalesce(Sum('weight'), Decimal('0'))
            )['total']
            sale.total_sale_price = rst.rst_final_price or Decimal('0')
            sale.save()
        
        return rst


class RSTCompletionSerializer(serializers.Serializer):
    """Serializer for completing an RST booking"""
    balance_payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    item_prices = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=2),
        help_text="Dictionary mapping item codes to their final prices"
    )
    
    def validate(self, data):
        rst = self.context['rst']
        item_codes = set(rst.rst_items.values_list('item__code', flat=True))
        price_codes = set(map(int, data['item_prices'].keys()))
        
        if item_codes != price_codes:
            missing = item_codes - price_codes
            extra = price_codes - item_codes
            error_msg = []
            if missing:
                error_msg.append(f"Missing prices for items: {list(missing)}")
            if extra:
                error_msg.append(f"Prices provided for non-RST items: {list(extra)}")
            raise serializers.ValidationError(" ".join(error_msg))
        
        return data
    
    def save(self):
        rst = self.context['rst']
        validated_data = self.validated_data
        
        with transaction.atomic():
            # Create SaleItems with prices
            total_price = Decimal('0')
            for rst_item in rst.rst_items.all():
                item_code = str(rst_item.item.code)
                price = validated_data['item_prices'][item_code]
                
                SaleItem.objects.create(
                    sale=rst.sale,
                    item=rst_item.item,
                    method=validated_data['balance_payment_method'],
                    purity_price=price
                )
                
                # Update item status
                rst_item.item.status = ItemStatus.SOLD
                rst_item.item.save()
                
                total_price += price
            
            # Calculate balance due
            balance_due = total_price - rst.rst_adv
            
            # Create balance payment
            SalePayment.objects.create(
                sale=rst.sale,
                method=validated_data['balance_payment_method'],
                amount=balance_due,
                kind=PaymentKind.RST_BALANCE
            )
            
            # Update RST
            rst.status = RSTStatus.COMPLETED
            rst.completed_at = timezone.now()
            rst.rst_final_price = total_price
            rst.rst_due = balance_due
            rst.save()
            
            # Update sale totals
            sale = rst.sale
            sale.total_sale_price = total_price
            sale.save()
        
        return rst


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order model to populate order details in sales"""
    class Meta:
        model = Order
        fields = ['id', 'number', 'assigned_to', 'is_completed', 'delivery_date']
    
    def create(self):
        with transaction.atomic():
            sale = Sales.objects.create()
            sale.save()
            order = Order.objects.create(
                sale=sale,
                number=sale.invoice_number,
                assigned_to=self.validated_data.get('assigned_to'),
                delivery_date=self.validated_data.get('delivery_date')
            )
            order.save()
            return order



class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            'id', 'business_date', 'category', 'description', 
            'amount', 'payment_method', 'sale', 'payment', 'created_at'
        ]


class SalesListSerializer(serializers.ModelSerializer):
    """Serializer for listing sales with basic details
    READ_ONLY
    """
    rst_status = serializers.CharField(source='rst_details.status', read_only=True)
    
    class Meta:
        model = Sales
        fields = [
            'id', 'business_date', 'invoice_number', 'customer_name', 'sold_by', 
            'item_count', 'total_weight', 'total_sale_price', 'is_rst', 'is_order', 'rst_status'
        ]


class SalesDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for a single sale, including items and payments
    READ_ONLY
    """
    items = SaleItemSerializer(many=True, read_only=True)
    payments = SalePaymentSerializer(many=True, read_only=True)
    order_details = OrderSerializer(read_only=True)
    rst_details = RSTSerializer(read_only=True)
    
    # Payment breakdown for RST
    advance_payments = serializers.SerializerMethodField()
    balance_payments = serializers.SerializerMethodField()

    class Meta:
        model = Sales
        fields = [
            'id', 'business_date', 'invoice_number', 'customer_name', 'sold_by',
            'item_count', 'total_weight', 'total_sale_price',
            'items', 'payments', 'is_rst', 'is_order', 
            'rst_details', 'order_details', 'advance_payments', 'balance_payments'
        ]
    
    def get_advance_payments(self, obj):
        advance_payments = obj.payments.filter(kind=PaymentKind.RST_ADVANCE)
        return SalePaymentSerializer(advance_payments, many=True).data
    
    def get_balance_payments(self, obj):
        balance_payments = obj.payments.filter(kind=PaymentKind.RST_BALANCE)
        return SalePaymentSerializer(balance_payments, many=True).data



class SaleRowSerializer(serializers.Serializer):
    business_date = serializers.DateField(required=True)
    invoice_number = serializers.IntegerField(required=True)
    customer = serializers.CharField(required=False, allow_blank=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)  # alias target
    sold_by = serializers.CharField(required=False, allow_blank=True)
    item_count = serializers.IntegerField(required=False, default=0)
    gold_weight = serializers.DecimalField(max_digits=12, decimal_places=3, required=False, default=Decimal('0'))
    sale_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    item_code = serializers.CharField(required=False, allow_blank=True)
    item = serializers.CharField(required=False, allow_blank=True)
    kdm_vori = serializers.CharField(required=False, allow_blank=True)
    gold_payment = serializers.CharField(required=False, allow_blank=True)
    cash_card_payment = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0'))
    customer_due = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0'))
    due_by = serializers.CharField(required=False, allow_blank=True)
    payment_type = serializers.CharField(required=False, allow_blank=True)

    def to_internal_value(self, data):
        # map 'customer' -> 'customer_name' if provided
        if data.get("customer") and not data.get("customer_name"):
            data = {**data, "customer_name": data["customer"]}
        return super().to_internal_value(data)
    

class SalesComposeSerializer(serializers.Serializer):
    """Serializer for creating regular sales (non-RST, non-Order)"""
    items = SaleRowSerializer(many=True) 

    def validate(self, attrs):
        rows = attrs["items"]
        # per-request duplicates
        seen = set()
        dupes = set()
        for r in rows:
            inv = r["invoice_number"]
            if inv in seen:
                dupes.add(inv)
            seen.add(inv)
        if dupes:
            raise serializers.ValidationError({"items": [f"duplicate invoice_number(s) in request: {sorted(dupes)}"]})
        # existing in DB
        existing = set(Sales.objects.filter(invoice_number__in=seen).values_list("invoice_number", flat=True))
        if existing:
            raise serializers.ValidationError({"items": [f"invoice_number(s) already exist: {sorted(existing)}"]})
        return attrs

    def create(self, validated_data):
        items_data = validated_data["items"]
        
        for row in items_data:
            with transaction.atomic():
                sale = Sales.objects.create(
                    business_date=row.get('business_date'),
                    customer_name=row.get('customer', ''),
                    sold_by=row.get('sold_by', ''),
                    invoice_number=row.get('invoice_number'),
                    item_count=row.get('item_count', 0),
                    total_weight=row.get('gold_weight', Decimal('0')),
                    total_sale_price=row.get('sale_price')
                )
                sale.save()

                # Create items
                item_codes, item_names = parse_item_codes(row.get('item_code'), row.get('item'))
                for idx, code in enumerate(item_codes):
                    name = item_names[idx] if idx < len(item_names) else ''
                    defaults = {
                        'purity': row.get('kdm_vori'),
                        'description': name,
                        'status': ItemStatus.SOLD
                    }
                    try:
                        item, created = Item.objects.get_or_create(code=code, defaults=defaults)
                    except IntegrityError:
                        item = Item.objects.get(code=code)
                        created = False
                    if not created and item.status != ItemStatus.SOLD:
                        item.status = ItemStatus.SOLD
                        item.save(update_fields=['status'])
                
                    sale_item = SaleItem.objects.create(
                        sale=Sales.objects.get(id=sale.id),
                        item=Item.objects.get(code=code),
                        purity_price=row.get('kdm_vori'),
                        description=name
                    )
                    sale_item.save()
                
                #Create payments
                payment = SalePayment.objects.create(
                    sale=Sales.objects.get(id=sale.id),
                    #TODO: Support multiple payment methods
                    method=PaymentMethod.CASH,
                    amount=row.get('cash_card_payment'),
                    description=row.get('payment_type', ''),
                    kind=PaymentKind.PAYMENT
                )
                payment.save()

                #parse the payment type
                pay_types = parse_payment_methods(row.get('payment_type', ''))
                if not pay_types:
                    pay_types = [PaymentMethod.CASH]
                for pay_type in pay_types:
                    payment = SalePayment.objects.create(
                        sale=Sales.objects.get(id=sale.id),
                        #TODO: Support accurate payment methods
                        method=[PaymentMethod.CASH],
                        amount=row.get('cash_card_payment'),
                        description=pay_type,
                        kind=PaymentKind.PAYMENT
                    )
                    payment.save()

                    has_gold_payment = row.get('gold_payment', '')
                    if not has_gold_payment == '' or pay_type.lower() == 'gold':
                        gold_payment = GoldPayment.objects.create(
                            payment=SalePayment.objects.get(id=payment.id),
                            weight=row.get('gold_payment'),
                            #TODO: Business Logic doesn't support the exact purity
                            purity='Not Specified'
                        )
                        gold_payment.save()

        return sale