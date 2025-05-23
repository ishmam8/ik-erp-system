import django.utils.timezone as timezone
from django.db import models
from django.contrib.auth.models import User

CURRENCY_CHOICES = (
    ('USD', 'USD'),
    ('UAE', 'UAE'),
    ('CAD', 'CAD'),
)


'''
Implementing a singleton pattern for GlobalSettings
This ensures that there is only one instance of GlobalSettings in the database
and it can be accessed globally.
'''
class GlobalSettings(models.Model):
    selected_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='USD',
        help_text="The currency used throughout the application."
    )
    
    def __str__(self):
        return f"Global Currency: {self.selected_currency if self.selected_currency else 'Not Set'}"

    @staticmethod
    def get_instance():
        # Get the singleton instance or create a default one
        instance, created = GlobalSettings.objects.get_or_create(
            defaults={"selected_currency": 'USD'}
        )
        return instance


'''
The Vault model represents a vault that hold the 22K gold.
It is created to track the amount of gold (g) bought in Dubai.
1 gram of gold represents 1 VGToken
'''
class Vault(models.Model):
    vgt_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    serial_number = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
    max_length=50, 
    choices=[('READY', 'Ready'), ('DEPLETED', 'Depleted')], 
    default='READY'
    )


'''
The GoldData model represents the 22K gold price data for each day.
'''
class GoldData(models.Model):
    serial_number = models.CharField(max_length=255, unique=True)
    gold_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    purity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)


'''
UserProfile model extends the default User model to include additional fields.
Given the custodian model, vgt_balance represents the amount of VGToken user owns.
The fiat_balance represents the amount of fiat currency in the system.
TODO: Need to store USDC or USDT in the database.
'''
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    #TODO:
    # How will we store the fiat balance in pratice?
    fiat_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    vgt_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    preferred_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        null=True,
        blank=True,
        help_text="The user's preferred currency."
    )


class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('MINT', 'Mint'),
        ('REDEEM', 'Redemption'),
        ('BUY', 'Purchase Fiat'),
        ('SELL', 'Sell Fiat'),
        ('TRANSFER', 'Transfer Token'),
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

    #VGToken was implemented as non decimal token
    #TODO:
    created_at = models.DateTimeField(default=timezone.now)
    vgt_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fiat_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    action = models.CharField(max_length=50, choices=TRANSACTION_TYPES, default='MINT')
    vault = models.ForeignKey(Vault, related_name='transactions', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True) 


#Transaction to track sending and receiving
'''More like a marketplace system where users can send VGToken to each other.
'''
class PendingTransaction(models.Model):
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_pending_transactions')
    target_email = models.EmailField()
    vgt_amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    created_at = models.DateTimeField(default=timezone.now)
    is_claimed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)