import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from api.accounting_ledger.views import SalesView
from accounting_ledger.models import Sales

@pytest.fixture
def factory():
    return APIRequestFactory()

@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="tester", password="pass")

@pytest.mark.django_db
def test_post_single_sale(factory, user):
    payload = {
        "date": "2025-10-24",
        "items": [
            {
                "invoice_number": "121",
                "customer": "imon",
                "quantity": "2",
                "item_code": "1499",
                "item": "necklace",
                "sold_by": "sophia",
                "gold_weight": "4.98",
                "is_rst": False,
                "kdm_vori": "22K/140000",
                "sale_price": "81000",
                "cash_card_payment": "80000",
                "gold_payment": "0.32=1000",
                "rst_payment": "",
                "rst_advanced": "",
                "customer_due": "",
                "due_by": "",
                "payment_type": "Cash/Gold",
            },
            {
                "invoice_number": "1234",
                "customer": "test",
                "quantity": "2",
                "item_code": "1499",
                "item": "necklace",
                "sold_by": "sophia",
                "gold_weight": "4.98",
                "is_rst": False,
                "kdm_vori": "22K/140000",
                "sale_price": "81000",
                "cash_card_payment": "80000",
                "gold_payment": "0.32=1000",
                "rst_payment": "",
                "rst_advanced": "",
                "customer_due": "",
                "due_by": "",
                "payment_type": "Cash/Gold",
            },
        ],
    }

    request = factory.post("/", payload, format="json")
    force_authenticate(request, user=user)
    response = SalesView.as_view()(request)

    assert response.status_code in (200, 201), getattr(response, "data", None)
    assert Sales.objects.count() == 2
