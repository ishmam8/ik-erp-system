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
    vgt_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)


class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('MINT', 'Mint'),
        ('BUY', 'Buy'),
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
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES)
    created_at = models.DateTimeField(default=timezone.now)
    vault = models.ForeignKey(Vault, related_name='transactions', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True) 


class PendingTransaction(models.Model):
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_pending_transactions')
    target_email = models.EmailField()
    vgt_amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    created_at = models.DateTimeField(default=timezone.now)
    is_claimed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)