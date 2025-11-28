import logging
from datetime import date
from django.db import transaction
from django.db.models import Prefetch
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from accounting_ledger.utils import to_decimal
from accounting_ledger.models import Artisan, ArtisanOrder, Supplier, SupplierOrder
logger = logging.getLogger("ledger.sales")

#test

class ArtisanBuyGoldView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        #check if artisan exists
        #state the method of buying gold

        artisans = Artisan.objects.all().values('artisan_id', 'artisan_name')
        return Response(artisans, status=status.HTTP_200_OK)