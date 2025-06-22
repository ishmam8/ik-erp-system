from django.shortcuts import render
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from core.models import UserProfile, Vault, Transaction


def get_fiat_balance(user_id):
    """
    Returns the fiat balance of a user.
    """
    try:
        # Get the user and their profile
        user = settings.AUTH_USER_MODEL.objects.get(id=user_id)
        user_profile = user.profile  # Access the related UserProfile using the related_name 'profile'

        # Return the fiat balance
        return {"username": user.username, "fiat_balance": user_profile.fiat_balance}
    except settings.AUTH_USER_MODEL.DoesNotExist:
        return {"error": "User does not exist."}
    except UserProfile.DoesNotExist:
        return {"error": "User profile does not exist for this user."}


def update_user_balance(user_id, new_balance):
    user = settings.AUTH_USER_MODEL.objects.get(id=user_id)
    user.profile.fiat_balance = new_balance
    user.profile.save()

    # Send WebSocket update
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_balance_{user_id}",
        {
            "type": "send_balance_update",
            "data": {
                "username": user.username,
                "fiat_balance": new_balance
            }
        }
    )