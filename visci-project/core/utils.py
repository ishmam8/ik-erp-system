from .models import GlobalSettings

def get_active_currency(user=None):
    if user and user.is_authenticated:
        user_profile = getattr(user, 'profile', None)
        if user_profile and user_profile.preferred_currency:
            return user_profile.preferred_currency
    
    # Fallback to global default currency
    global_settings = GlobalSettings.get_instance()
    return global_settings.selected_currency if global_settings and global_settings.selected_currency else 'USD'

def switch_currency(user, new_currency_code):
    """
    Switch the user's preferred currency to a new one.
    """
    from .models import CURRENCY_CHOICES, UserProfile

    # Validate the new currency code
    if not any(code == new_currency_code for code, _ in CURRENCY_CHOICES):
        return f"Currency {new_currency_code} is not a valid currency code."

    try:
        # Update the user's preferred currency
        user_profile = getattr(user, 'profile', None)
        if user_profile:
            user_profile.preferred_currency = new_currency_code
            user_profile.save()

            #TODO: Implement conversion rate logic
                # Update fiat balances or any other currency-dependent values
                # Example: Convert fiat balance to the new currency (pseudo-code)
                # Assuming you have a conversion rate function
                # conversion_rate = get_conversion_rate(user_profile.preferred_currency.currency, new_currency_code)
                # user_profile.fiat_balance *= conversion_rate
                # user_profile.save()

        return f"Currency switched to {new_currency_code} for user {user.username}"
    except Exception as e:
        return f"An error occurred: {str(e)}"