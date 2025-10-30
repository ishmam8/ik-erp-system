import pytest
import json
from pprint import pprint
import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.renderers import JSONRenderer
from api.accounting_ledger.views import SalesView
from accounting_ledger.models import Order, RST, Item, RSTItem, Sales, SaleItem, SalePayment, GoldPayment

@pytest.fixture
def factory():
    return APIRequestFactory()

@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="tester", password="pass")

def _print_response(response):
    print("\n=== API RESPONSE ===")
    try:
        print(JSONRenderer().render(response.data).decode())
    except Exception as e:
        print(e)
        print(response.data)

def _print_db_snapshot():
    print("\n=== DB SNAPSHOT ===")
    items = list(
        Item.objects.order_by("code").values(
            "code", "purity", "description", "status","created_at", "updated_at",
        )
    )
    sales = list(
        Sales.objects.order_by("id").values(
            "id", "business_date", "invoice_number", "customer_name",
            "sold_by", "item_count", "total_weight", "total_sale_price",
        )
    )
    sale_items = list(
        SaleItem.objects.order_by("sale_id", "id").values(
            "id", "sale_id", "item__code", "description", "purity_price",
        )
    )
    payments = list(
        SalePayment.objects.order_by("sale_id", "id").values(
            "id", "sale_id", "method", "amount", "due_amount", "due_by", "kind", "description",
        )
    )
    golds = list(
        GoldPayment.objects.order_by("payment__sale_id", "id").values(
            "id", "payment_id", "payment__sale_id", "weight", "purity",
        )
    )
    rst=list(
        RST.objects.order_by("id").values(
          "id","sale_id","rst_adv",  
        )
    )
    rst_items=list(
        RSTItem.objects.order_by("rst_id").values(
          "rst_id","item", 
        )
    )
    order=list(
        Order.objects.order_by("sale_id").values(
          "sale_id","assigned_to","is_completed","delivery_date",
          "completed_at","item_description" 
        )
    )
    print("\n-- Items --")
    pprint(items)
    print("\n-- Sales --")
    pprint(sales)
    print("\n-- SaleItems --")
    pprint(sale_items)
    print("\n-- SalePayments --")
    pprint(payments)
    print("\n-- GoldPayments --")
    pprint(golds)
    print("\n-- RSTPayments --")
    pprint(rst)
    print("\n-- RSTItemPayments --")
    pprint(rst_items)
    print("\n-- Order --")
    pprint(order)


@pytest.mark.django_db
def test_post_single_sale(factory, user):
    """Test posting a single sale via the SalesView API endpoint."""
    payload = {
        "date": "2025-10-24",
        "items": [
            {
                "invoice_number": "121",
                "customer": "imon",
                "quantity": "2",
                "item_code": "(1499)(1500)",
                "item": "necklace,ring",
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
                "payment_type": "Cash,Gold",
            },
            {
                "invoice_number": "02192",
                "customer": "test",
                "quantity": "1",
                "item_code": "1324",
                "item": "necklace",
                "sold_by": "sophia",
                "gold_weight": "6.3",
                "is_rst": False,
                "kdm_vori": "22K/140000",
                "sale_price": "81000",
                "cash_card_payment": "80000",
                "gold_payment": "",
                "rst_payment": "",
                "rst_advanced": "",
                "customer_due": "",
                "due_by": "",
                "payment_type": "Cash",
            },
        ],
    }

    request = factory.post("/", payload, format="json")
    force_authenticate(request, user=user)
    response = SalesView.as_view()(request)

    _print_response(response)

    assert response.status_code in (200, 201), getattr(response, "data", None)
    assert Sales.objects.count() == 2

    # Show DB contents (sales + related)
    _print_db_snapshot()

    # Optional tighter assertions on response body
    # assert sorted(r["invoice_number"] for r in response.data["results"]) == [121, 1234]
    assert response.data["errors"] == []


@pytest.mark.django_db
def test_post_single_rst(factory, user):
    """Test posting a single rst sale via the SalesRSTView API endpoint."""
    payload = {
        "date": "2025-10-24",
        "items": [
            {
                "invoice_number": "4239",
                "customer": "imon",
                "quantity": "2",
                "item_code": "(2399)(1098)",
                "item": "necklace,chain",
                "sold_by": "sophia",
                "gold_weight": "4.98",
                "is_rst": True,
                "kdm_vori": "22K/140000",
                "sale_price": "RST",
                "cash_card_payment": "20000",
                "gold_payment": "0.32=1000",
                "rst_payment": "20000",
                "rst_advanced": "",
                "customer_due": "",
                "due_by": "",
                "payment_type": "Cash,Gold",
            },
        ],
    }

    request = factory.post("/", payload, format="json")
    force_authenticate(request, user=user)
    response = SalesView.as_view()(request)

    _print_response(response)

    assert response.status_code in (200, 201), getattr(response, "data", None)
    assert RST.objects.count() == 1
    assert Sales.objects.count() == 1

    # Show DB contents (sales + related)
    _print_db_snapshot()

    # Optional tighter assertions on response body
    # assert sorted(r["invoice_number"] for r in response.data["results"]) == [121, 1234]
    assert response.data["errors"] == []


@pytest.mark.django_db
def test_post_single_order(factory, user):
    """Test posting a single order sale via the SalesView API endpoint."""
    payload = {
        "date": "2025-10-24",
        "items": [
            {
                "invoice_number": "121",
                "customer": "imon",
                "quantity": "2",
                "item_code": "",
                "item": "",
                "sold_by": "sophia",
                "gold_weight": "",
                "is_rst": False,
                "kdm_vori": "",
                "sale_price": "order",
                "cash_card_payment": "0",
                "gold_payment": "0.32=1000",
                "rst_payment": "",
                "rst_advanced": "",
                "customer_due": "",
                "due_by": "",
                "payment_type": "Gold,No Cash",
                "order_assigned_to": "Rahman",
                "order_delivery_date": "2025-10-29",
                "is_completed": False,
                "order_items":"Ring",
            },
        ],
    }

    request = factory.post("/", payload, format="json")
    force_authenticate(request, user=user)
    response = SalesView.as_view()(request)

    _print_response(response)

    assert response.status_code in (200, 201), getattr(response, "data", None)
    assert Order.objects.count() == 1

    # Show DB contents (sales + related)
    _print_db_snapshot()

    # Optional tighter assertions on response body
    # assert sorted(r["invoice_number"] for r in response.data["results"]) == [121, 1234]
    assert response.data["errors"] == []
