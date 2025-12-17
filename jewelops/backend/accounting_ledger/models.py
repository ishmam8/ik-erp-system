import uuid
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from decimal import Decimal

ENUMERATE_PAYMENT_METHODS = [
    ('CASH', 'Cash'),
    ('CARD', 'Card'),
    ('GOLD', 'Gold'),
    ('RST', 'RST Booking'),
]

class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    CARD = "CARD", "Card"
    GOLD = "GOLD", "Gold"
    RST  = "RST",  "RST Booking"

class PaymentKind(models.TextChoices):
    PAYMENT = "PAYMENT", "Payment"
    REFUND  = "REFUND",  "Refund"
    RST_ADVANCE = "RST_ADVANCE", "RST Advance Payment"
    RST_BALANCE  = "RST_BALANCE",  "RST Balance Payment"

class ExpenseCategory(models.TextChoices):
    REFUND_ORDER  = "REFUND_ORDER", "Refund – Order"
    REFUND_RST    = "REFUND_RST", "Refund – RST"
    GOLD_CASHBACK = "GOLD_CASHBACK", "Gold Cashback"
    OTHER         = "OTHER", "Other"

class ItemStatus(models.TextChoices):
    AVAILABLE = "AVAILABLE", "Available"
    RST_BOOKED = "RST_BOOKED", "RST Booked"
    SOLD      = "SOLD",      "Sold"
    RETURNED  = "RETURNED",  "Returned"
    VOIDED   = "VOIDED",   "Voided"

class RSTStatus(models.TextChoices):
    BOOKED = "BOOKED", "Booked (Partial Payment)"
    COMPLETED = "COMPLETED", "Completed (Full Payment)"
    VOIDED = "VOIDED", "Voided"

class AcidGoldSource(models.TextChoices):
    TATI_BAZAR = "TATI_BAZAR", "artisan tati bazaar"
    MELTING_GOLD = "MELTING_GOLD", "store melting gold"
    BOUGHT_GOLD = "BOUGHT_GOLD", "store bought gold"


class Item(models.Model):
    ''' Represents an individual inventory item '''
    code = models.IntegerField(unique=True, primary_key=True)
    purity = models.CharField(max_length=50)
    weight = models.DecimalField(
        max_digits=10, 
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Weight of the item, can be null if not measured yet")
    description = models.TextField()
    note = models.TextField(blank=True) 
    status = models.CharField(max_length=200, choices=ItemStatus.choices, default=ItemStatus.AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    #FK
    recovery_gold = models.ForeignKey(
        "RecoveryGold",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    karigar_order = models.ForeignKey(
        "ArtisanOrders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    supplier_order = models.ForeignKey(
        "SupplierOrders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )

    def __str__(self):
        return f"Item {self.code} - {self.purity} - {self.weight}g - {self.status}"


class Sales(models.Model):
    business_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    invoice_number = models.IntegerField(
        unique=True,
        null=False,
    )
    customer_name = models.CharField(max_length=255) #TODO: Change to ForeignKey when Customer model is created
    sold_by = models.CharField(max_length=100)
    item_count = models.IntegerField(default=0, editable=False)
    total_weight = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0, 
        editable=False)
    total_sale_price = models.CharField(max_length=100, blank=True)
    
    @property
    def is_rst(self):
        return hasattr(self, 'rst_details')
    
    @property
    def is_order(self):
        return hasattr(self, 'order_details')


class SalePayment(models.Model):
    ''' Records individual payment methods and amount for a sale'''
    sale = models.ForeignKey(Sales, related_name='payments', on_delete=models.CASCADE)
    method = models.CharField(max_length=50, choices=PaymentMethod.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(null=True, blank=True, help_text="Additional details like card type or gold description")
    kind = models.CharField(max_length=200, choices=PaymentKind.choices, default=PaymentKind.PAYMENT)
    due_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="The remaining amount due after this payment")
    due_by = models.CharField(max_length=100, null=True)


class SaleItem(models.Model):
    sale = models.ForeignKey(Sales, related_name='items', on_delete=models.CASCADE)
    item = models.ForeignKey(Item, null=False, related_name='item', on_delete=models.PROTECT)
    purity_price = models.CharField(
        null=True,
        blank=True,
        help_text="Price on market rate at the time of business date")
    description = models.TextField(blank=True)


class GoldPayment(models.Model):
    ''' Records payments made via Gold'''
    payment = models.OneToOneField(
        SalePayment, 
        related_name='gold', 
        on_delete=models.CASCADE,
        limit_choices_to={'method': 'GOLD'},
    )
    weight = models.CharField(max_length=100)
    purity = models.CharField(max_length=50)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.payment.method != 'GOLD':
            raise ValidationError("GoldPayment must link to a SalePayment with method='GOLD'.")


class RST(models.Model):
    sale = models.OneToOneField(Sales, on_delete=models.CASCADE, related_name='rst_details')
    rst_adv = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Advance payment made for RST booking")
    rst_due = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Remaining amount for RST booking")
    rst_final_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When RST was completed")
    status = models.CharField(max_length=100, choices=RSTStatus.choices, default=RSTStatus.BOOKED)

    @property
    def number(self):
        return self.sale.invoice_number


class RSTItem(models.Model):
    rst = models.ForeignKey(RST, related_name='rst_items', on_delete=models.CASCADE)
    item = models.ForeignKey(Item, null=False, related_name='items', on_delete=models.PROTECT)
    description = models.TextField(blank=True)


class RSTVoided(models.Model):
    rst = models.OneToOneField(RST, on_delete=models.CASCADE, related_name='voided_info')
    voided_at = models.DateTimeField(auto_now_add=True)


class Order(models.Model):
    sale = models.OneToOneField(Sales, on_delete=models.CASCADE, related_name='order_details')
    assigned_to = models.CharField(max_length=100)
    is_completed = models.BooleanField(default=False)
    delivery_date = models.DateField(null=True, blank=True, help_text="Expected delivery date for the order")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When the order was completed")
    item_description = models.CharField(max_length=200, blank=True)

    def clean(self):
        """Check for Order Completion"""
        super().clean()
        if self.is_completed:
            sale = self.sale
            if not sale.items.exists():
                raise ValidationError("Cannot complete an order with no items.")
            bad = sale.items.filter(
                Q(code__isnull=True) |
                Q(weight__isnull=True) | Q(weight__lte=0) |
                Q(purity_price__isnull=True) | Q(purity_price__lt=0)
            )
            if bad.exists():
                raise ValidationError(
                    {"is_completed": "All items must have code, positive weight, and price before completion."}
                )
    
    @property
    def number(self):
        return self.sale.invoice_number

    def save(self, *args, **kwargs):
        # Ensure validation also runs outside ModelForms/DRF
        self.full_clean()
        return super().save(*args, **kwargs)


class Expense(models.Model):
    business_date  = models.DateField()
    created_at     = models.DateField(auto_now_add=True)
    category       = models.CharField(max_length=200, choices=ExpenseCategory.choices, default=ExpenseCategory.OTHER)
    expense_type   = models.CharField(max_length=200, null=False, default='store-exp')
    description    = models.TextField(blank=True)
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=100, choices=PaymentMethod.choices)


# -------------- SUPPLIERS -----------------


class Supplier(models.Model):
    supplier_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200, null=False)
    cash_outstanding_balance = models.DecimalField(max_digits=10,decimal_places=2,null=False)
    last_audit_date = models.DateField(null=False)
    last_transaction_date = models.DateField(null=False)

    def __str__(self):
        return self.name


class SupplierOrders(models.Model):
    '''
    This table holds information about suppliers' delivering jewellery
    '''
    class SupplierTransactionType(models.TextChoices):
        PAYMENT = "PAYMENT", "receive payment"
        DELIVER = "DELIVER", "deliver jewellery"

    order_id = models.AutoField(primary_key=True)
    supplier = models.ForeignKey(Supplier, related_name='orders', on_delete=models.DO_NOTHING)
    date = models.DateField(help_text='Jewellery delivery date')
    j_total_weight = models.DecimalField(max_digits=10, decimal_places=2)
    j_total_value = models.CharField()
    transaction_type = models.CharField(max_length=20,choices=SupplierTransactionType.choices)
    purchase_rate_per_bhori = models.CharField(max_length=20,blank=True,
        null=True,
        help_text="Set only when transaction_type=DELIVER",)
    batch_id = models.CharField()
    note = models.TextField(blank=True)

    #when doing cleaning, 
    # we must make sure that if the order kind is raw gold purchase
    # the outstanding balance is updated with new gold value 
    #
    def __str__(self):
        return f"SupplierOrder {self.order_id} – {self.supplier.name}"


class SupplierCashbook(models.Model):
    cashbook_payment_id = models.AutoField(primary_key=True)
    supplier = models.ForeignKey(Supplier, related_name='cashbook', on_delete=models.DO_NOTHING)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    supplier_order = models.OneToOneField(
        SupplierOrders,
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # or DO_NOTHING, but PROTECT is safer
        related_name="cashbook_entries",
    )

    #Clean:
    # we must make sure that if there is a payment received
    # the outstanding balance is updated with new gold value 
    def __str__(self):
        return f"SupplierPayment {self.cashbook_payment_id} – {self.supplier.name}"


# -------------- MELTING GOLD -----------
class MeltingGoldBook(models.Model):
    id = models.AutoField(primary_key=True)
    date_period = models.DurationField()
    j_back_to_store = models.DecimalField(max_digits=10,
        decimal_places=2)
    gold_for_melting = models.DecimalField(max_digits=10,
        decimal_places=2)
    recovery_gold = models.DecimalField(max_digits=10,
        decimal_places=2)
    recovery_date = models.DateField()

    def __str__(self):
        return f"MeltingGoldBook {self.id}"
    

class RecoveryGold(models.Model):
    id = models.AutoField(primary_key=True)
    melting_gold_book = models.ForeignKey(
        MeltingGoldBook,
        on_delete=models.CASCADE,
        related_name="recovery_records",
    )
    gold_to_artisan_weight = models.DecimalField(max_digits=10,
        decimal_places=2)
    owner_withdrawn_gold_weight = models.DecimalField(max_digits=10,
        decimal_places=2, blank=True)
    owner_withdrawn_gold_value = models.IntegerField(null=True, blank=True)
    exchange_to_store_gold = models.DecimalField(max_digits=10, decimal_places=2,
        help_text='Exchanged the amount of gold to jewellery and back to store')
    note = models.TextField(
        blank=True,
        help_text="Mention pre/post recovery exchange.",
    )

    def __str__(self):
        return f"RecoveryGold {self.id}"
    

# ---------- STORE ITEM TRANSFER -----------
class StoreItemTransfer(models.Model):
    class TransferType(models.TextChoices):
        OUT = "OUT", "Out"
        IN = "IN", "In"

    id = models.AutoField(primary_key=True)
    store = models.CharField(max_length=100)
    date_of_transfer = models.DateField()
    type_of_transfer = models.CharField(
        max_length=20, choices=TransferType.choices
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="store_transfers",
    )
    foreign_store_itemcode = models.CharField(max_length=100)

    def __str__(self):
        return f"Transfer {self.id} – {self.item.code}"
    






#------ ARTISANS --------

class Artisan(models.Model):
    name = models.CharField(max_length=200, null=False)
    jewellery_balance_g = models.DecimalField(
        max_digits=10, 
        decimal_places=3, 
        default=0, 
        help_text='Running gold balance in grams. Positive: artisan owes jewellery. Negative: we owe gold.') 
    cash_outstanding = models.DecimalField(null=False, max_digits=12, decimal_places=2, default=0)
    last_audit_date = models.DateField(null=False)
    last_transaction_date = models.DateField(null=False)

    def __str__(self):
        return self.name

    @property
    def pending_jewellery_g(self) -> Decimal:
        return max(self.jewellery_balance_g, Decimal("0"))

    @property
    def gold_owed_to_artisan_g(self) -> Decimal:
        return max(-self.jewellery_balance_g, Decimal("0"))

    #have a property function which updates the cash_outstanding whenever there is a payment done
    # or order received 
    #have a property function which updates the pending_jewellery whenever there is a jewellery update
    

class ArtisanOrders(models.Model):
    '''
    This table holds information about artisans' buying gold and delivering jewellery orders
    '''
    class ArtisanTransactionType(models.TextChoices):
        RAW_G = "RAW_G", "receive raw gold, order_kind=RECEIVE"
        DELIVER_J = "DELIVER_J", "deliver jewellery, order_kind=PROVIDE"

    order_id = models.AutoField(primary_key=True)
    artisan = models.ForeignKey(Artisan, related_name='orders', on_delete=models.PROTECT)
    date = models.DateField()
    total_weight = models.DecimalField(max_digits=10,decimal_places=2)
    
    transaction_type = models.CharField(
        max_length=20,choices=ArtisanTransactionType.choices)
    purchase_rate_per_bhori = models.CharField(max_length=20,blank=True,
        null=True,
        help_text="Set only when order_kind = RECEIVE",)
    total_gold_value = models.CharField(
        null=True,
        help_text="Total value of gold received, transaction_type = RECEIVE"
    )
    
    receive_source = models.CharField(
        max_length=20,
        choices=AcidGoldSource.choices,
        blank=True,
        null=True,
        help_text="Set only when transaction_type = RECEIVE",
    )

    item_category = models.CharField(null=True, blank=True, max_length=50)
    note = models.TextField(null=True)
    gold_from_melting_recovery = models.ForeignKey(RecoveryGold,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="artisan_orders",
    )
    invoice_number = models.CharField(max_length=100, null=True, blank=True, db_index=True)


class ArtisanCashbook(models.Model):
    cashbook_payment_id = models.AutoField(primary_key=True)
    artisan = models.ForeignKey(Artisan, related_name='cashbook', on_delete=models.PROTECT)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_date = models.DateTimeField()
    artisan_order = models.ForeignKey(
        ArtisanOrders,
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # or DO_NOTHING, but PROTECT is safer
        related_name="cash_payments",
    )

    #Clean:
    # we must make sure that if there is a payment received
    # the outstanding balance is updated with new gold value 

