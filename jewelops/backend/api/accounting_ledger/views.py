from datetime import date
from django.db import transaction
from django.db.models import Prefetch
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny

from api.accounting_ledger.serializers import OrderComposeSerializer, RSTBookingSerializer, \
    SalesComposeSerializer, SalesListSerializer, ExpenseComposeSerializer, ExpenseListSerializer
from accounting_ledger.utils import to_decimal

import logging

from accounting_ledger.models import Expense, SaleItem, Sales
from services.process_sales import process_sales_rows
from services.process_expenses import process_expenses_rows
logger = logging.getLogger("ledger.sales")


class SalesView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        rows = request.data.get("sales") or []
        order_rows = request.data.get("orders") or []
        business_date = request.data.get("date")
        
        results, errors = process_sales_rows(rows, order_rows, business_date, request.user)

        # Return success response
        return Response({
            "message": "Sales data received successfully!",
            "received_data": request.data,
            "user": str(request.user),
            "results": results,
            "errors": errors,
        }, status=status.HTTP_200_OK)
    

class SalesGetView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        month_str = request.query_params.get("month")
        include_items = request.query_params.get("include_items") == "true"

        # simple pagination guards
        try:
            limit = int(request.query_params.get("limit", 200))  # sane default
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response({"detail": "limit and offset must be integers"}, status=status.HTTP_400_BAD_REQUEST)

        qs = Sales.objects.all().order_by("id")
        if month_str and month_str not in ("undefined", "null", ""):
            # expect "YYYY-MM"
            parts = month_str.split("-")
            if len(parts) != 2:
                return Response({"detail": "month must be in YYYY-MM format"}, status=status.HTTP_400_BAD_REQUEST)
            year, month = parts
            try:
                year = int(year)
                month = int(month)
            except ValueError:
                return Response({"detail": "month must be in YYYY-MM format"}, status=status.HTTP_400_BAD_REQUEST)

            qs = qs.filter(business_date__year=year, business_date__month=month)

        # prefetch conditionally
        if include_items:
            qs = qs.prefetch_related(
                Prefetch(
                    "items",  # related_name on SaleItem.sale
                    queryset=SaleItem.objects.select_related("item")
                )
            )

        # also prefetch rst/order so serializer doesn't N+1
        qs = qs.select_related("rst_details", "order_details")

        # 4) apply pagination slice
        qs = qs[offset:offset + limit]

        serializer = SalesListSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class ExpensesView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        rows = request.data.get("payouts") or []
        business_date = request.data.get("date")
        
        # print("=" * 50)
        # print("EXPENSES REQUEST RECEIVED")
        # print(f"User: {request.user}")
        # print(f"Data: {request.data}")
        # print(f"Headers: {request.headers}")
        # print("=" * 50)

        rows, errors = process_expenses_rows(request.user, rows, business_date)
        return Response({
            "message": "Sales data received successfully!",
            "received_data": request.data,
            "user": str(request.user),
        }, status=status.HTTP_200_OK)


class ExpensesGetView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        month_str = request.query_params.get("month")
        include_items = request.query_params.get("include_items") == "true"

        # simple pagination guards
        try:
            limit = int(request.query_params.get("limit", 200))  # sane default
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response({"detail": "limit and offset must be integers"}, status=status.HTTP_400_BAD_REQUEST)

        qs = Expense.objects.all().order_by("id")
        if month_str and month_str not in ("undefined", "null", ""):
            # expect "YYYY-MM"
            parts = month_str.split("-")
            if len(parts) != 2:
                return Response({"detail": "month must be in YYYY-MM format"}, status=status.HTTP_400_BAD_REQUEST)
            year, month = parts
            try:
                year = int(year)
                month = int(month)
            except ValueError:
                return Response({"detail": "month must be in YYYY-MM format"}, status=status.HTTP_400_BAD_REQUEST)

            qs = qs.filter(business_date__year=year, business_date__month=month)

        qs = qs[offset:offset + limit]

        serializer = ExpenseListSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)