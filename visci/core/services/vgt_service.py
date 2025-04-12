import hashlib
import uuid
from django.db import transaction, models
from django.contrib.auth.models import User
from core.models import PendingTransaction, UserProfile, Vault, Transaction


def _generate_serial_number():
    #TODO: determine how to use the serial number
    '''Generates a unique serial number for the vault.'''
    return hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()[:8]

@transaction.atomic
def create_vault(initial_gold=0.00, serial_number=None):
    '''Creates a new vault with an initial gold amount.'''
    if serial_number is None:
        serial_number = _generate_serial_number()
    try:
        vault = Vault.objects.create(
            vgt_balance=initial_gold,
            serial_number=serial_number,
        )
        Transaction.objects.create(
            vault=vault,
            transaction_type='MINT',
            vgt_amount=initial_gold,
            notes='Initial deposit'
        )
        return vault
    except Exception as e:
        raise Exception(f'Failed to create vault: {e}')

@transaction.atomic
def add_vgt_to_vault(vault, amount=0.00, description=""):
    '''Adds gold to an existing vault.'''

    vault.vgt_balance += amount
    vault.save()
    Transaction.objects.create(
        vault=vault,
        transaction_type='VAULT_DEPOSIT',
        vgt_amount=amount,
        notes=description
    )

@transaction.atomic
def remove_vgt_from_vault(vault, amount=0.00, description=""):
    '''Removes gold from an existing vault.'''

    if vault.vgt_balance < amount:
        raise Exception("Insufficient gold in vault.")
    
    vault.vgt_balance -= amount
    vault.save()
    Transaction.objects.create(
        vault=vault,
        transaction_type='VAULT_WITHDRAWAL',
        vgt_amount=-amount,
        notes=description
    )

@transaction.atomic
def get_vault_balance(vault):
    '''Returns the current balance of the vault.'''
    balance = Transaction.objects.filter(vault=vault).aggregate(models.Sum('amount'))['amount__sum'] or 0
    return balance

@transaction.atomic
def user_buy_vgt(vault, user, amount=0.00):
    #TDOO: Is this amount in gold or fiat money?
    # If it's in fiat money, are we converting it to gold?
    # require another function to convert fiat to gold

    '''Allows a user to buy VGT.'''
    vault = Vault.objects.filter(status='READY').first()
    user_profile = UserProfile.objects.get(user=user)

    if vault.vgt_balance >= amount and user_profile.is_active:
        vault.vgt_balance -= amount
        vault.save()
        user_profile.vgt_balance += amount
        user_profile.save()
        
        Transaction.objects.create(
            actor=user,
            vgt_amount=amount,
            transaction_type='BUY',
            notes=f'User purchases {amount} VGT',
            vault=vault
        )
        return True
    else:
        return False

@transaction.atomic
def user_send_vgt(user, target_email, amount=0.00):
    # the target user might not have yet created a profile

    user_profile = UserProfile.objects.get(user=user)
    target_profile = UserProfile.objects.get(user=target_user)

    if user_profile.vgt_balance <= amount:
        raise Exception("Insufficient balance to send VGT.")
    
    try:
        #check if the target user has an account
        target_user = User.objects.get(email=target_email)
        target_profile = UserProfile.objects.get(user=target_user)

        if not target_profile.is_active:
            raise Exception("Target user's profile is inactive.")
        
        user_profile.vgt_balance -= amount
        user_profile.save()

        target_profile.vgt_balance += amount
        target_profile.save()

        Transaction.objects.create(
            actor=user,
            target_user=target_user,
            vgt_amount=amount,
            transaction_type='GIFT_SENT',
            notes=f'User sends {amount} VGT to {target_email}'
        )
        return True
    
    except User.DoesNotExist:
        # If the target user does not exist, create a pending transaction
        PendingTransaction.objects.create(
            actor=user,
            target_email=target_email,
            vgt_amount=amount,
            notes=f'User sends {amount} VGT to {target_email}'
        )
        user_profile.vgt_balance -= amount
        user_profile.save()

        #TODO: Send email to target user with a link to claim the VGT
        # This would require a function to send emails
        # send_email(target_email, amount)

        return True

def user_redeem_vgt(user, amount=0.00):
    '''Allows a user to redeem VGT.'''
    user_profile = UserProfile.objects.get(user=user)

    if user_profile.vgt_balance >= amount:
        user_profile.vgt_balance -= amount
        user_profile.save()

        Transaction.objects.create(
            actor=user,
            vgt_amount=-amount,
            transaction_type='REDEEM',
            notes=f'User redeems {amount} VGT'
        )
        return True
    else:
        return False