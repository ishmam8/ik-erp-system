import json
from decimal import Decimal
from pprint import pprint

import pytest

from accounting_ledger.models import (
    Artisan,
    ArtisanOrders,
    ArtisanCashbook,
    AcidGoldSource,
)

# 🔴 PLACEHOLDER: update this import path to your actual services module
from services.supply_chain import (
    apply_artisan_order_effects,
    apply_artisan_payment_effects,
)


def _print_db_snapshot():
    print("\n=== ARTISAN LEDGER SNAPSHOT ===")

    artisans = list(
        Artisan.objects.order_by("id").values(
            "id",
            "name",
            "pending_jewellery_weight",
            "cash_outstanding",
            "last_audit_date",
            "last_transaction_date",
        )
    )
    orders = list(
        ArtisanOrders.objects.order_by("order_id").values(
            "order_id",
            "artisan_id",
            "date",
            "total_weight",
            "transaction_type",
            "purchase_rate_per_bhori",
            "total_gold_value",
            "receive_source",
            "item_category",
            "note",
        )
    )
    cashbook = list(
        ArtisanCashbook.objects.order_by("cashbook_payment_id").values(
            "cashbook_payment_id",
            "artisan_id",
            "payment_amount",
            "payment_date",
            "artisan_order_id",
        )
    )

    print("\n-- Artisans --")
    pprint(artisans)
    print("\n-- ArtisanOrders --")
    pprint(orders)
    print("\n-- ArtisanCashbook --")
    pprint(cashbook)


@pytest.fixture
def today():
    import datetime as _dt
    return _dt.date(2025, 10, 24)


@pytest.fixture
def artisan(today):
    return Artisan.objects.create(
        name="Test Artisan",
        pending_jewellery_weight=Decimal("0.000"),
        cash_outstanding=Decimal("0.00"),
        last_audit_date=today,
        last_transaction_date=today,
    )


@pytest.mark.django_db
def test_artisan_buys_gold_from_own(artisan, today):
    """
    ARTISAN BUYS GOLD TO MAKE JEWELLERY:
    - total_gold_value auto-calculated from grams & rate_per_bhori
    - pending_jewellery_weight increases by weight
    - cash_outstanding increases by that computed value
    """
    order = ArtisanOrders.objects.create(
        artisan=artisan,
        date=today,
        total_weight=Decimal("11.664"),  # 1 bhori
        transaction_type=ArtisanOrders.ArtisanTransactionType.RAW_G,
        purchase_rate_per_bhori="1000.00",  # per bhori
        # total_gold_value intentionally LEFT BLANK so service will compute it
        # total_gold_value=11664,
        receive_source=AcidGoldSource.TATI_BAZAR,
        item_category="RING",
        note="Buys own gold to make jewellery",
    )

    apply_artisan_order_effects(order)
    artisan.refresh_from_db()
    order.refresh_from_db()

    _print_db_snapshot()

    assert order.total_gold_value == "1000.00"
    assert artisan.pending_jewellery_weight == Decimal("11.664")
    assert artisan.cash_outstanding == Decimal("1000.00")


@pytest.mark.django_db
def test_artisan_gets_melting_gold(artisan, today):
    """
    ARTISAN GETS RAW MELTING GOLD:
    - total_gold_value auto-calculated from grams & acid rate per bhori
    - pending_jewellery_weight increases by weight
    - cash_outstanding increases by that computed value
    """
    order = ArtisanOrders.objects.create(
        artisan=artisan,
        date=today,
        total_weight=Decimal("23.328"),  # 2 bhori
        transaction_type=ArtisanOrders.ArtisanTransactionType.RAW_G,
        purchase_rate_per_bhori="800.00",  # acid rate per bhori
        # total_gold_value=0,
        receive_source=AcidGoldSource.MELTING_GOLD,
        item_category="CHAIN",
        note="Receives melting gold from store",
    )

    apply_artisan_order_effects(order)
    artisan.refresh_from_db()
    order.refresh_from_db()

    _print_db_snapshot()

    # 2 bhori * 800 = 1600
    assert order.total_gold_value == "1600.00"
    assert artisan.pending_jewellery_weight == Decimal("23.328")
    assert artisan.cash_outstanding == Decimal("1600.00")


@pytest.mark.django_db
def test_artisan_delivers_jewellery_can_go_negative(artisan, today):
    """
    ARTISAN DELIVERS JEWELLERY:
    - pending_jewellery_weight decreases by delivered weight
    - can go negative if delivery > outstanding
    - cash_outstanding unchanged
    """
    # First, give artisan some outstanding jewellery and cash via RAW_G
    initial = ArtisanOrders.objects.create(
        artisan=artisan,
        date=today,
        total_weight=Decimal("3.000"),
        transaction_type=ArtisanOrders.ArtisanTransactionType.RAW_G,
        purchase_rate_per_bhori="100.00",
        total_gold_value="0.00",
        receive_source=AcidGoldSource.TATI_BAZAR,
        item_category="RING",
        note="Initial own gold",
    )
    apply_artisan_order_effects(initial)
    artisan.refresh_from_db()

    assert artisan.pending_jewellery_weight == Decimal("3.000")
    # assert artisan.cash_outstanding == Decimal("300.00")

    # Now artisan delivers more jewellery weight than outstanding (5 > 3)
    deliver = ArtisanOrders.objects.create(
        artisan=artisan,
        date=today,
        total_weight=Decimal("5.000"),
        transaction_type=ArtisanOrders.ArtisanTransactionType.DELIVER_J,
        total_gold_value="600.00",
        item_category="MIXED",
        note="Over-delivery to test negative pending jewellery",
    )
    apply_artisan_order_effects(deliver)
    artisan.refresh_from_db()

    _print_db_snapshot()

    # 3 - 5 = -2
    assert artisan.pending_jewellery_weight == Decimal("-2.000")
    # cash_outstanding unchanged by delivery

@pytest.mark.django_db
def test_artisan_receives_payment_reduces_cash_outstanding(artisan, today):
    """
    ARTISAN RECEIVES PAYMENT (valid):
    - cash_outstanding reduced by payment_amount
    - no error if payment <= outstanding
    """
    artisan.cash_outstanding = Decimal("1200.00")
    artisan.save(update_fields=["cash_outstanding"])

    payment = ArtisanCashbook.objects.create(
        artisan=artisan,
        payment_amount=Decimal("500.00"),
        artisan_order=None,
    )

    apply_artisan_payment_effects(payment)
    artisan.refresh_from_db()

    _print_db_snapshot()

    assert artisan.cash_outstanding == Decimal("700.00")


@pytest.mark.django_db
def test_artisan_payment_more_than_outstanding_raises_error(artisan, today):
    """
    ARTISAN RECEIVES PAYMENT (invalid):
    - if payment > cash_outstanding, raise ValueError
    - cash_outstanding must remain unchanged
    """
    artisan.cash_outstanding = Decimal("300.00")
    artisan.save(update_fields=["cash_outstanding"])

    payment = ArtisanCashbook.objects.create(
        artisan=artisan,
        payment_amount=Decimal("500.00"),
        artisan_order=None,
    )

    with pytest.raises(ValueError, match="exceeds artisan's cash outstanding"):
        apply_artisan_payment_effects(payment)

    artisan.refresh_from_db()
    _print_db_snapshot()

    assert artisan.cash_outstanding == Decimal("300.00")
