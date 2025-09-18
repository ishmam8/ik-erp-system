from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError

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

class ExpenseCategory(models.TextChoices):
    REFUND_ORDER = "REFUND_ORDER", "Refund – Order"
    REFUND_RST   = "REFUND_RST",   "Refund – RST"
    OTHER        = "OTHER",        "Other"

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
    total_sale_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        editable=False)
    
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
    kind = models.CharField(max_length=10, choices=PaymentKind.choices, default=PaymentKind.PAYMENT)


class SaleItem(models.Model):
    sale = models.ForeignKey(Sales, related_name='items', on_delete=models.CASCADE)
    purity = models.CharField(max_length=50)
    method  = models.CharField(max_length=10, choices=PaymentMethod.choices)
    code = models.IntegerField(
        null=True, 
        blank=True, 
        unique=True,
        help_text="Item code within the sale, can be null for order items"
    )
    weight = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Weight of the item, can be null for order items"
    )
    purity_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price on market rate at the time of business date")
    description = models.TextField()


class GoldPayment(models.Model):
    ''' Records payments made via Gold'''
    payment = models.OneToOneField(
        SalePayment, 
        related_name='gold', 
        on_delete=models.CASCADE,
        limit_choices_to={'method': 'GOLD'},
    )
    weight = models.DecimalField(max_digits=10, decimal_places=2)
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

    @property
    def number(self):
        return self.sale.invoice_number


class RSTItem(models.Model):
    rst = models.ForeignKey(RST, related_name='rst_items', on_delete=models.CASCADE)
    code = models.IntegerField(help_text="Item code within the RST booking")
    purity = models.CharField(max_length=50)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['rst','code'], name='uniq_rst_code')
        ]

class RSTVoided(models.Model):
    rst = models.OneToOneField(RST, on_delete=models.CASCADE, related_name='voided_info')
    voided_at = models.DateTimeField(auto_now_add=True)


class Order(models.Model):
    sale = models.OneToOneField(Sales, on_delete=models.CASCADE, related_name='order_details')
    number = models.CharField(max_length=50, unique=True, help_text="Order number same as invoice number")
    assigned_to = models.CharField(max_length=100)
    is_completed = models.BooleanField(default=False)
    delivery_date = models.DateField(null=True, blank=True, help_text="Expected delivery date for the order")

    def clean(self):
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
    
    def save(self, *args, **kwargs):
        # Ensure validation also runs outside ModelForms/DRF
        self.full_clean()
        return super().save(*args, **kwargs)


class Expense(models.Model):
    business_date  = models.DateField()
    created_at     = models.DateTimeField(auto_now_add=True)
    category       = models.CharField(max_length=20, choices=ExpenseCategory.choices, default=ExpenseCategory.OTHER)
    description    = models.TextField(blank=True)
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)

    # optional traceability (recommended)
    sale    = models.ForeignKey(Sales, null=True, blank=True, on_delete=models.SET_NULL)
    payment = models.OneToOneField('SalePayment', null=True, blank=True, on_delete=models.SET_NULL)