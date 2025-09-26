from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers
from accounting_ledger.models import (
    Item, Sales, SaleItem, SalePayment, GoldPayment, RST, RSTItem, RSTVoided, 
    Order, Expense, PaymentMethod, PaymentKind, ExpenseCategory, ItemStatus, RSTStatus
)


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
            'id', 'sale', 'item', 'method', 'purity_price', 'item_details'
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


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['id', 'number', 'assigned_to', 'is_completed', 'delivery_date']


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            'id', 'business_date', 'category', 'description', 
            'amount', 'payment_method', 'sale', 'payment', 'created_at'
        ]


class SalesListSerializer(serializers.ModelSerializer):
    """Serializer for listing sales with basic details"""
    rst_status = serializers.CharField(source='rst_details.status', read_only=True)
    
    class Meta:
        model = Sales
        fields = [
            'id', 'business_date', 'invoice_number', 'customer_name', 'sold_by', 
            'item_count', 'total_weight', 'total_sale_price', 'is_rst', 'is_order', 'rst_status'
        ]


class SalesDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for a single sale, including items and payments"""
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


class SalesComposeSerializer(serializers.ModelSerializer):
    """Serializer for creating regular sales (non-RST, non-Order)"""
    items = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        write_only=True
    )
    payments = SalePaymentSerializer(many=True, write_only=True)

    class Meta:
        model = Sales
        fields = [
            'id', 'business_date', 'invoice_number', 'customer_name', 'sold_by',
            'items', 'payments'
        ]

    def validate(self, data):
        items = data.get('items', [])
        payments = data.get('payments', [])
        
        # Calculate totals
        total_item_price = Decimal('0')
        for item_data in items:
            total_item_price += Decimal(str(item_data.get('purity_price', '0')))
        
        total_payment_amount = Decimal('0')
        for payment in payments:
            total_payment_amount += payment.get('amount', Decimal('0'))

        if total_item_price != total_payment_amount:
            raise serializers.ValidationError(
                f"Total item prices ({total_item_price}) must equal total payments ({total_payment_amount})"
            )
        
        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        payments_data = validated_data.pop('payments', [])

        with transaction.atomic():
            sale = Sales.objects.create(**validated_data)

            # Create items (either existing items or new items for orders)
            for item_data in items_data:
                item_code = item_data.get('item_code')
                if item_code:
                    # Existing item
                    item = Item.objects.get(code=item_code)
                    item.status = ItemStatus.SOLD
                    item.save()
                else:
                    # New item (for orders that are being completed)
                    item = Item.objects.create(
                        code=item_data['code'],
                        purity=item_data['purity'],
                        weight=item_data.get('weight'),
                        description=item_data['description'],
                        status=ItemStatus.SOLD
                    )
                
                SaleItem.objects.create(
                    sale=sale,
                    item=item,
                    method=item_data['method'],
                    purity_price=item_data['purity_price']
                )

            # Create payments
            for payment_data in payments_data:
                SalePayment.objects.create(sale=sale, **payment_data)

            # Update sale aggregates
            sale.item_count = sale.items.count()
            sale.total_weight = sale.items.aggregate(
                total_weight=Coalesce(Sum('item__weight'), Decimal('0'))
            )['total_weight']
            sale.total_sale_price = sale.items.aggregate(
                total_price=Coalesce(Sum('purity_price'), Decimal('0'))
            )['total_price']
            sale.save()

        return sale