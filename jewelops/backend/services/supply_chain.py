# services.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from accounting_ledger.models import Artisan, ArtisanOrders, ArtisanCashbook, AcidGoldSource, Supplier, SupplierCashbook, SupplierOrders

BHORI_IN_GRAMS = Decimal("11.664")

def _as_decimal(value) -> Decimal:
    """
    Safely convert CharField/DecimalField to Decimal.
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@transaction.atomic
def apply_artisan_order_effects(order: ArtisanOrders) -> None:
    """
    Apply business rules for an ArtisanOrders row to the Artisan balances.
    Handles:
    - RAW_G: artisan receives raw gold (own gold or melting gold)
    - DELIVER_J: artisan delivers jewellery
    """
    artisan = order.artisan
    total_weight = _as_decimal(order.total_weight)

    # RAW GOLD: artisan now owes jewellery (weight) and is owed gold value
    if order.transaction_type == ArtisanOrders.ArtisanTransactionType.RAW_G:
        if not order.purchase_rate_per_bhori:
            raise ValueError("purchase_rate_per_bhori must be set for RAW_G transactions.")

        rate_per_bhori = _as_decimal(order.purchase_rate_per_bhori)

        # grams → bhori, then multiply by rate
        bhori = (total_weight / BHORI_IN_GRAMS)
        total_gold_value_dec = (bhori * rate_per_bhori)

        # Persist calculation so it's visible in DB
        order.total_gold_value = str(total_gold_value_dec.quantize(Decimal("0.00")))
        order.save(update_fields=["total_gold_value"])
        
        artisan.pending_jewellery_weight += total_weight
        artisan.cash_outstanding += total_gold_value_dec


    # DELIVER JEWELLERY: reduce outstanding jewellery weight
    elif order.transaction_type == ArtisanOrders.ArtisanTransactionType.DELIVER_J:
        artisan.pending_jewellery_weight -= total_weight

    # Update last transaction date
    artisan.last_transaction_date = order.date
    artisan.save(update_fields=["pending_jewellery_weight", "cash_outstanding", "last_transaction_date"])


@transaction.atomic
def apply_artisan_payment_effects(entry: ArtisanCashbook) -> None:
    """
    Apply business rules when an Artisan receives payment.
    - Decrease cash_outstanding by payment_amount
    """
    artisan = entry.artisan
    amount = _as_decimal(entry.payment_amount or 0)

    if (artisan.cash_outstanding - amount) < Decimal("0"):
        raise ValueError("Payment amount exceeds artisan's cash outstanding.")
    
    artisan.cash_outstanding -= amount
    artisan.last_transaction_date = entry.payment_date.date()
    artisan.save(update_fields=["cash_outstanding", "last_transaction_date"])


def apply_supplier_order_effects(order: SupplierOrders) -> None:
    """
    SUPPLIER BRINGS JEWELLERY (DELIVER):

    - Expects SupplierOrders with transaction_type = DELIVER.
    - Reads j_total_value (already set at current rate).
    - Increases supplier.cash_outstanding_balance by that value.
    - Updates last_transaction_date to the order date.

    If you want to use transaction_type=PAYMENT on SupplierOrders later,
    you can extend this, but right now we only treat DELIVER as a payable.
    """
    supplier: Supplier = order.supplier

    # Only do ledger logic for deliveries (supplier brings jewellery)
    if order.transaction_type != SupplierOrders.SupplierTransactionType.DELIVER:
        # No-op for now; you can extend for PAYMENT-type orders later if needed.
        return

    total_value = _as_decimal(order.j_total_value)

    supplier.cash_outstanding_balance += total_value
    supplier.last_transaction_date = order.date

    supplier.save(
        update_fields=[
            "cash_outstanding_balance",
            "last_transaction_date",
        ]
    )


@transaction.atomic
def apply_supplier_payment_effects(entry: SupplierCashbook) -> None:
    """
    SUPPLIER RECEIVES PAYMENT:

    - Decreases supplier.cash_outstanding_balance by payment_amount.
    - Raises ValueError if payment_amount > current outstanding (no negative balances).
    - Updates last_transaction_date to the payment date.
    """
    supplier: Supplier = entry.supplier
    amount = _as_decimal(entry.payment_amount or 0)

    if amount <= 0:
        raise ValueError("Payment amount must be positive.")

    new_balance = supplier.cash_outstanding_balance - amount
    if new_balance < Decimal("0"):
        raise ValueError("Payment amount exceeds supplier's outstanding balance.")

    supplier.cash_outstanding_balance = new_balance
    supplier.last_transaction_date = entry.payment_date.date()

    supplier.save(
        update_fields=[
            "cash_outstanding_balance",
            "last_transaction_date",
        ]
    )
