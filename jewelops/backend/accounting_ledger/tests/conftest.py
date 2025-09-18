import pytest
from decimal import Decimal
from datetime import date, datetime
from django.test import TestCase
from accounting_ledger.models import (
    Sales, SaleItem, SalePayment, GoldPayment, RST, RSTItem, RSTVoided,
    Order, Expense, PaymentMethod, PaymentKind, ExpenseCategory
)

@pytest.fixture
def sample_sale():
    """Create a basic sale instance for testing"""
    return Sales.objects.create(
        business_date=date.today(),
        invoice_number=12345,
        customer_name="John Doe",
        sold_by="Rahman"
    )

@pytest.fixture
def sample_sale_with_rst():
    """Create a basic sale instance for testing"""
    return Sales.objects.create(
        business_date=date.today(),
        invoice_number=12347,
        customer_name="Kohinoor",
        sold_by="Sunny"
    )


@pytest.fixture
def sample_sale_with_totals():
    """Create a sale with calculated totals"""
    return Sales.objects.create(
        business_date=date.today(),
        invoice_number=12346,
        customer_name="Jane Smith",
        sold_by="Sales Person",
        item_count=2,
        total_weight=Decimal('10.50'),
        total_sale_price=Decimal('1000.00')
    )


@pytest.fixture
def sample_sale_payment(sample_sale):
    """Create a basic sale payment"""
    return SalePayment.objects.create(
        sale=sample_sale,
        method=PaymentMethod.CASH,
        amount=Decimal('500.00'),
        description="Cash payment",
        kind=PaymentKind.PAYMENT
    )
#sale payment with two methods? what if there are more than two methods?


@pytest.fixture
def sample_gold_payment(sample_sale):
    """Create a gold payment with associated SalePayment"""
    sale_payment = SalePayment.objects.create(
        sale=sample_sale,
        method=PaymentMethod.GOLD,
        amount=Decimal('10000.00'),
        kind=PaymentKind.PAYMENT
    )
    return GoldPayment.objects.create(
        payment=sale_payment,
        weight=Decimal('10.00'),
        purity="22K"
    )


@pytest.fixture
def sample_rst(sample_sale_with_rst):
    """Create an RST booking"""
    return RST.objects.create(
        sale=sample_sale_with_rst,
        rst_adv=Decimal('500.00'),
        rst_due=Decimal('1500.00'),
        rst_final_price=Decimal('2000.00'),
        delivery_date=date.today()
    )


@pytest.fixture
def sample_order(sample_sale):
    """Create an order"""
    return Order.objects.create(
        sale=sample_sale,
        number=sample_sale.invoice_number,
        assigned_to="Worker A",
        is_completed=False,
        delivery_date=date.today()
    )
