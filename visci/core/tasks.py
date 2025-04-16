import requests
from datetime import timedelta
from django.utils.timezone import now
from django.db import transaction
from .models import PendingTransaction, Transaction


def check_expiry():
    """
    Checks for expired transactions from the PendingTransaction table.
    - Marks them as expired.
    - Moves back the vgt_amount to the sender's balance.
    - Notifies the sender, target user, and admin via email.
    - Deletes the expired transaction.
    """
    expired_transactions = PendingTransaction.objects.filter(is_claimed=False)

    for pending_transaction in expired_transactions:
        expiry_date = pending_transaction.created_at + timedelta(days=30)
        if now() > expiry_date:
            with transaction.atomic():
                # TDOD:
                # Notify sender, target user, and admin (implement email logic here)
                # Example: send_email_to_user(pending_transaction.actor.email, ...)

                # Move back the vgt_amount to the sender's balance
                user_profile = pending_transaction.actor.profile  # Assuming `UserProfile` is related via `profile`
                user_profile.vgt_balance += pending_transaction.vgt_amount
                user_profile.save()

                # Track the transaction
                Transaction.objects.create(
                    actor=pending_transaction.actor,
                    vgt_amount=pending_transaction.vgt_amount,
                    transaction_type='GIFT_SEND_BACK',
                    notes=f'Pending transaction expired. Amount returned to {pending_transaction.actor.email}',
                )

                # Delete the expired transaction
                pending_transaction.delete()

def fetch_gold_to_cad():
    METALPRICE_API_KEY = '3a61a079fb42b5c3d4fa5a7eb2cf3475'  # Keep this secret!
    API_URL = 'https://api.metalpriceapi.com/v1/latest'
    
    params = {
        'api_key': METALPRICE_API_KEY,
        'base': 'CAD',  # First get USD rates
        'currencies': 'XAU'  # Get both CAD and gold (XAU) rates
    }

    try:
        response = requests.get(API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("success"):
            rate = data["rates"]["CADXAU"]
            print(f"1 ounce of XAU(Gold) = ${rate} CAD")  # Note this is per troy ounce, not gram
            return rate
        else:
            raise Exception(data.get("error", "Failed to fetch rate"))

    except Exception as e:
        print(f"Error in fetch_gold_to_cad: {e}")
        return None

def convert_vgt_to_fiat():
    pass