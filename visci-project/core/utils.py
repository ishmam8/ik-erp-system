from .models import Currency, GlobalSettings

def get_active_currency(user=None):
    if user and user.is_authenticated:
        user_profile = getattr(user, 'profile', None)
        if user_profile and user_profile.preferred_currency:
            return user_profile.preferred_currency.currency
    
    # Fallback to global default currency
    global_settings = GlobalSettings.objects.first()
    return global_settings.selected_currency.currency if global_settings and global_settings.selected_currency else 'USD'

def switch_currency(user, new_currency_code):
    """
    Switch the user's preferred currency to a new one.
    """
    try:
        # Get the new currency object
        new_currency = Currency.objects.get(currency=new_currency_code)

        # Update the user's preferred currency
        user_profile = getattr(user, 'profile', None)
        if user_profile:
            user_profile.preferred_currency = new_currency
            user_profile.save()

            #TODO: Implement conversion rate logic
                # Update fiat balances or any other currency-dependent values
                # Example: Convert fiat balance to the new currency (pseudo-code)
                # Assuming you have a conversion rate function
                # conversion_rate = get_conversion_rate(user_profile.preferred_currency.currency, new_currency_code)
                # user_profile.fiat_balance *= conversion_rate
                # user_profile.save()

        return f"Currency switched to {new_currency_code} for user {user.username}"
    except Currency.DoesNotExist:
        return f"Currency {new_currency_code} does not exist."
    except Exception as e:
        return f"An error occurred: {str(e)}"