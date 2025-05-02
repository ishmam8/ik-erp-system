import django.utils.timezone as timezone
from django.db import models
from django.contrib.auth.models import User


class Vault(models.Model):
    vgt_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    serial_number = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
    max_length=50, 
    choices=[('READY', 'Ready'), ('DEPLETED', 'Depleted')], 
    default='READY'
    )


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    fiat_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    vgt_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    stop_limit = models.DecimalField(
        max_digits=5,  # Allows values up to 999.99%
        decimal_places=2,  # Two decimal places for precision
        default=0.00,  # Default percentage value
        help_text="Stop limit as a percentage (e.g., 50.00 for 50%)"
    )
    is_active = models.BooleanField(default=True)

# currency = USD
# gold api ~ 1 ounce
# 1 vgt token ~ 1 gram of gold
# 1 ounce of gold = 28.3495 grams
class GoldData(models.Model):
    serial_number = models.CharField(max_length=255, unique=True)
    gold_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    purity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

#     def post(self, request):
#         # Assuming you have a serializer for GoldData
#         serializer = GoldDataSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#     def delete(self, request, pk):
#         try:
#             gold_data = GoldData.objects.get(pk=pk)
#             gold_data.delete()
#             return Response(status=status.HTTP_204_NO_CONTENT)
#         except GoldData.DoesNotExist:
#             return Response(status=status.HTTP_404_NOT_FOUND)
#     def get(self, request):
#         gold_data = GoldData.objects.all()
#         serializer = GoldDataSerializer(gold_data, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)


class Currency(models.Model):
    CURRENCY_CHOICES = (
        ('USD', 'USD'),
        ('UAE', 'UAE'),
        ('CAD', 'CAD'),
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, unique=True)
    created_at = models.DateTimeField(default=timezone.now)


class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('MINT', 'Mint'),
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('GIFT_SENT', 'Gift Sent'),
        ('GIFT_RECEIVED', 'Gift Received'),
        ('GIFT_SEND_BACK', 'Gift Send Back'),
        ('REDEEM', 'Redeem'),
        ('VAULT_DEPOSIT', 'Vault Deposit'),
        ('VAULT_WITHDRAWAL', 'Vault Withdrawal'),
    )
    # Who initiated the action?
    actor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,  # Keep transactions if user leaves
        null=True,
        related_name='actions_initiated'
    )
    
    # Who was affected? (e.g., receiver of a gift)
    target_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='actions_received'
    )

    vgt_amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    action = models.CharField(max_length=50, choices=TRANSACTION_TYPES, default='MINT')
    created_at = models.DateTimeField(default=timezone.now)
    vault = models.ForeignKey(Vault, related_name='transactions', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True) 


#Transaction to track sending and receiving
class PendingTransaction(models.Model):
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_pending_transactions')
    target_email = models.EmailField()
    vgt_amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    created_at = models.DateTimeField(default=timezone.now)
    is_claimed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)