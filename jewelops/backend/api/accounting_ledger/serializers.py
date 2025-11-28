from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.forms import model_to_dict
from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from accounting_ledger.models import (
    Item, Sales, SaleItem, SalePayment, GoldPayment, RST, RSTItem, RSTVoided, 
    Order, Expense, PaymentMethod, PaymentKind, ExpenseCategory, ItemStatus, RSTStatus
)
from accounting_ledger.utils import parse_item_codes, parse_payment_methods
from services.sales_service import create_sales_from_row

# Serializer Check for individual rows in requesta
class SaleOrderRowSerializer(serializers.Serializer):
    business_date = serializers.DateField(required=True)
    invoice_number = serializers.IntegerField(required=True)
    customer = serializers.CharField(required=False, allow_blank=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)  # alias target
    sold_by = serializers.CharField(required=False, allow_blank=True)
    item_count = serializers.IntegerField(required=False, default=0)
    gold_weight = serializers.DecimalField(max_digits=12, decimal_places=3, required=False, default=Decimal('0'))
    sale_price = serializers.CharField(required=False, allow_blank=True)
    item_code = serializers.CharField(required=False, allow_blank=True)
    item = serializers.CharField(required=False, allow_blank=True)
    kdm_vori = serializers.CharField(required=False, allow_blank=True)
    gold_payment = serializers.CharField(required=False, allow_blank=True)
    cash_card_payment = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0'))
    customer_due = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0'))
    due_by = serializers.CharField(required=False, allow_blank=True)
    payment_type = serializers.CharField(required=False, allow_blank=True)
    rst_booking_payment = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0'))
    rst_adv = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0'))
    
    order_description = serializers.CharField(required=False, allow_blank=True)
    assigned_to = serializers.CharField(required=False, allow_blank=True)
    is_completed = serializers.BooleanField(required=False, default=False)
    delivery_date = serializers.DateField(required=False, allow_null=True)
    completed_at = serializers.DateField(required=False, allow_null=True)
    item_description = serializers.CharField(required=False, allow_blank=True)

    def to_internal_value(self, data):
        # map 'customer' -> 'customer_name' if provided
        if data.get("customer") and not data.get("customer_name"):
            data = {**data, "customer_name": data["customer"]}
        return super().to_internal_value(data)
    
class SaleRowSerializer(serializers.Serializer):
    business_date = serializers.DateField(required=True)
    invoice_number = serializers.IntegerField(required=True)
    customer = serializers.CharField(required=False, allow_blank=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)  # alias target
    sold_by = serializers.CharField(required=False, allow_blank=True)
    item_count = serializers.IntegerField(required=False, default=0)
    gold_weight = serializers.DecimalField(max_digits=12, decimal_places=3, required=False, default=Decimal('0'))
    sale_price = serializers.CharField(required=False, allow_blank=True)
    item_code = serializers.CharField(required=False, allow_blank=True)
    item = serializers.CharField(required=False, allow_blank=True)
    kdm_vori = serializers.CharField(required=False, allow_blank=True)
    gold_payment = serializers.CharField(required=False, allow_blank=True)
    cash_card_payment = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0'))
    customer_due = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0'))
    due_by = serializers.CharField(required=False, allow_blank=True)
    payment_type = serializers.CharField(required=False, allow_blank=True)
    rst_booking_payment = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0'))
    rst_adv = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0'))
    rst_order = serializers.CharField(required=False, allow_blank=True)
    
    def to_internal_value(self, data):
        # map 'customer' -> 'customer_name' if provided
        if data.get("customer") and not data.get("customer_name"):
            data = {**data, "customer_name": data["customer"]}
        return super().to_internal_value(data)

class ExpenseRowSerializer(serializers.Serializer):
    business_date = serializers.DateField(required=True)
    category = serializers.CharField(required=False, allow_blank=True)
    expense_type = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    payment_method = serializers.CharField(required=False, allow_blank=True)

# --------------------------------------  

# --------- MODEL SERIALIZERS ----------
class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = [
            'code', 'purity', 'weight', 'description', 'status', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


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
    item_details = ItemSerializer(source="item",read_only=True)

    class Meta:
        model = RSTItem
        # we don't need to expose `rst` here; parent RST has the list
        fields = ["id", "description", "item_details"]


class RSTVoidedSerializer(serializers.ModelSerializer):
    class Meta:
        model = RSTVoided
        fields = ["voided_at"]


class RSTSerializer(serializers.ModelSerializer):
    # from RSTItem.rst → related_name='rst_items'
    rst_items = RSTItemSerializer(many=True, read_only=True)
    # from RSTVoided.rst → related_name='voided_info'
    voided_info = RSTVoidedSerializer(read_only=True)
    # map to the @property `number` on the model
    number = serializers.IntegerField(read_only=True)

    class Meta:
        model = RST
        fields = ["id","status","rst_adv","rst_due","rst_final_price",
            "delivery_date","completed_at","number","rst_items",
            "voided_info",
        ]


class OrderSerializer(serializers.ModelSerializer):
    # expose the invoice number from the related sale
    number = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        # sale is implied via number / related_name, so we usually don't expose sale id here
        fields = [
            "id",
            "assigned_to",
            "is_completed",
            "delivery_date",
            "completed_at",
            "item_description",
            "number",
        ]
        read_only_fields = fields


class SaleItemSerializer(serializers.ModelSerializer):
    # Include item details for read operations
    item_details = ItemSerializer(source="item",read_only=True)
    
    class Meta:
        model = SaleItem
        fields = [
            'id', 'sale', 'item', 'purity_price', 'item_details'
        ]


class SalesListSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    rst_details = RSTSerializer(read_only=True)
    order_details = OrderSerializer(read_only=True)
    is_rst = serializers.SerializerMethodField()
    is_order = serializers.SerializerMethodField()

    class Meta:
        model = Sales
        fields = ["id","invoice_number","business_date","customer_name","sold_by",
            "item_count","total_weight","total_sale_price","is_rst","rst_details", "order_details", 
            "is_order","items",
        ]

    def get_is_rst(self, obj):
        return hasattr(obj, "rst_details")

    def get_is_order(self, obj):
        return hasattr(obj, "order_details")


class ExpenseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ["id","business_date", "category", "expense_type", "description", "amount", "payment_method"]


# ----------- COMPOSE SERIALIZERS -------------   

class SalesComposeSerializer(serializers.Serializer):
    row = SaleRowSerializer()

    def create(self, validated_data):
        sale = create_sales_from_row(validated_data["row"], item_status=ItemStatus.SOLD)
        return sale[-1]
    
    
class RSTBookingSerializer(serializers.Serializer):
    """Specialized serializer for creating RST bookings"""
    row = SaleRowSerializer()
        
    def create(self, validated_data):
        rst_sale = create_sales_from_row(validated_data["row"], item_status=ItemStatus.RST_BOOKED)
        return rst_sale[-1]
    

class OrderComposeSerializer(serializers.Serializer):
    row = SaleOrderRowSerializer()
    
    def create(self, validated_data):
        v_row = validated_data["row"]
        sale = create_sales_from_row(validated_data["row"], item_status=ItemStatus.SOLD)
        sale_instance = sale[-1]

        existing_order = Order.objects.filter(sale=sale_instance).first()
        if existing_order:
            # Just reuse the sale; process_sales_rows will treat this row as "handled"
            return sale_instance
        #TODO:
        # sale_payment = SalePayment.objects.create
        print("ASSIGNED TO", v_row.get('assigned_to')) 
        order = Order.objects.create(
            sale=sale_instance,
            assigned_to=v_row.get('assigned_to'),
            is_completed=v_row.get('is_completed', False),
            #TODO: delivery date might fail in format
            delivery_date=v_row.get('delivery_date'),
            item_description=v_row.get('order_description')
            #TODO: tackle when a order has been completed
        )
        return sale[-1]
    

class ExpenseComposeSerializer(serializers.Serializer):
    """Specialized serializer for creating RST bookings"""
    row = ExpenseRowSerializer()
        
    def create(self, validated_data):
        v_row = validated_data["row"]
        expenses = Expense.objects.create(
            business_date=v_row.get('business_date'),
            expense_type=v_row.get('expense_type'),
            description=v_row.get('description'),
            amount=v_row.get('amount'),
            payment_method=v_row.get('payment_method')
        )
        return expenses

# ---------------  ----------------  







# class RSTCompletionSerializer(serializers.Serializer):
#     """Serializer for completing an RST booking"""
#     balance_payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
#     item_prices = serializers.DictField(
#         child=serializers.DecimalField(max_digits=10, decimal_places=2),
#         help_text="Dictionary mapping item codes to their final prices"
#     )
    
#     def validate(self, data):
#         rst = self.context['rst']
#         item_codes = set(rst.rst_items.values_list('item__code', flat=True))
#         price_codes = set(map(int, data['item_prices'].keys()))
        
#         if item_codes != price_codes:
#             missing = item_codes - price_codes
#             extra = price_codes - item_codes
#             error_msg = []
#             if missing:
#                 error_msg.append(f"Missing prices for items: {list(missing)}")
#             if extra:
#                 error_msg.append(f"Prices provided for non-RST items: {list(extra)}")
#             raise serializers.ValidationError(" ".join(error_msg))
        
#         return data
    
#     def save(self):
#         rst = self.context['rst']
#         validated_data = self.validated_data
        
#         with transaction.atomic():
#             # Create SaleItems with prices
#             total_price = Decimal('0')
#             for rst_item in rst.rst_items.all():
#                 item_code = str(rst_item.item.code)
#                 price = validated_data['item_prices'][item_code]
                
#                 SaleItem.objects.create(
#                     sale=rst.sale,
#                     item=rst_item.item,
#                     method=validated_data['balance_payment_method'],
#                     purity_price=price
#                 )
                
#                 # Update item status
#                 rst_item.item.status = ItemStatus.SOLD
#                 rst_item.item.save()
                
#                 total_price += price
            
#             # Calculate balance due
#             balance_due = total_price - rst.rst_adv
            
#             # Create balance payment
#             SalePayment.objects.create(
#                 sale=rst.sale,
#                 method=validated_data['balance_payment_method'],
#                 amount=balance_due,
#                 kind=PaymentKind.RST_BALANCE
#             )
            
#             # Update RST
#             rst.status = RSTStatus.COMPLETED
#             rst.completed_at = timezone.now()
#             rst.rst_final_price = total_price
#             rst.rst_due = balance_due
#             rst.save()
            
#             # Update sale totals
#             sale = rst.sale
#             sale.total_sale_price = total_price
#             sale.save()
        
#         return rst


# class SalesDetailSerializer(serializers.ModelSerializer):
#     """Detailed serializer for a single sale, including items and payments
#     READ_ONLY
#     """
#     items = SaleItemSerializer(many=True, read_only=True)
#     payments = SalePaymentSerializer(many=True, read_only=True)
#     # order_details = OrderComposeSerializer(read_only=True)
#     rst_details = RSTSerializer(read_only=True)
    
#     # Payment breakdown for RST
#     advance_payments = serializers.SerializerMethodField()
#     balance_payments = serializers.SerializerMethodField()

#     class Meta:
#         model = Sales
#         fields = [
#             'id', 'business_date', 'invoice_number', 'customer_name', 'sold_by',
#             'item_count', 'total_weight', 'total_sale_price',
#             'items', 'payments', 'is_order', 
#             'rst_details', 'order_details', 'advance_payments', 'balance_payments'
#         ]
    
#     def get_advance_payments(self, obj):
#         advance_payments = obj.payments.filter(kind=PaymentKind.RST_ADVANCE)
#         return SalePaymentSerializer(advance_payments, many=True).data
    
#     def get_balance_payments(self, obj):
#         balance_payments = obj.payments.filter(kind=PaymentKind.RST_BALANCE)
#         return SalePaymentSerializer(balance_payments, many=True).data


# class RSTCompletionSerializer(serializers.Serializer):
#     """Serializer for completing an RST booking"""
#     balance_payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
#     item_prices = serializers.DictField(
#         child=serializers.DecimalField(max_digits=10, decimal_places=2),
#         help_text="Dictionary mapping item codes to their final prices"
#     )
    
#     def validate(self, data):
#         rst = self.context['rst']
#         item_codes = set(rst.rst_items.values_list('item__code', flat=True))
#         price_codes = set(map(int, data['item_prices'].keys()))
        
#         if item_codes != price_codes:
#             missing = item_codes - price_codes
#             extra = price_codes - item_codes
#             error_msg = []
#             if missing:
#                 error_msg.append(f"Missing prices for items: {list(missing)}")
#             if extra:
#                 error_msg.append(f"Prices provided for non-RST items: {list(extra)}")
#             raise serializers.ValidationError(" ".join(error_msg))
        
#         return data
    
#     def save(self):
#         rst = self.context['rst']
#         validated_data = self.validated_data
        
#         with transaction.atomic():
#             # Create SaleItems with prices
#             total_price = Decimal('0')
#             for rst_item in rst.rst_items.all():
#                 item_code = str(rst_item.item.code)
#                 price = validated_data['item_prices'][item_code]
                
#                 SaleItem.objects.create(
#                     sale=rst.sale,
#                     item=rst_item.item,
#                     method=validated_data['balance_payment_method'],
#                     purity_price=price
#                 )
                
#                 # Update item status
#                 rst_item.item.status = ItemStatus.SOLD
#                 rst_item.item.save()
                
#                 total_price += price
            
#             # Calculate balance due
#             balance_due = total_price - rst.rst_adv
            
#             # Create balance payment
#             SalePayment.objects.create(
#                 sale=rst.sale,
#                 method=validated_data['balance_payment_method'],
#                 amount=balance_due,
#                 kind=PaymentKind.RST_BALANCE
#             )
            
#             # Update RST
#             rst.status = RSTStatus.COMPLETED
#             rst.completed_at = timezone.now()
#             rst.rst_final_price = total_price
#             rst.rst_due = balance_due
#             rst.save()
            
#             # Update sale totals
#             sale = rst.sale
#             sale.total_sale_price = total_price
#             sale.save()
        
#         return rst
