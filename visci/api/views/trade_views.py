from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from core.utils import get_active_currency, switch_currency

@api_view(['GET'])
def get_currency_view(request):
    """
        API endpoint to get the active currency for the user. 
    """
    try:
        currency = get_active_currency(request.user)
        return Response({"currency": currency}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['POST'])
def switch_currency_view(request):
    """
    API endpoint to switch the user's preferred currency.
    """
    new_currency_code = request.data.get('currency')
    if not new_currency_code:
        return Response({"error": "Currency code is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = switch_currency(request.user, new_currency_code)
        return Response({"message": result}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)