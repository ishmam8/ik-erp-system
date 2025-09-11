from datetime import timezone
from django.db import transaction
from django.db.models import Sum, Count, F, DecimalField
from django.db.models.functions import Coalesce
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from .models import Expense, ExpenseCategory, PaymentKind, SalePayment, Sales, SaleItem

def _recompute_sales_aggregates(sale_id: int | None):
    """
    Recompute and update the item_count, total_weight, and total_sale_price
    for the given Sales instance.
    """
    agg = SaleItem.objects.filter(sale_id=sale_id).aggregate(
        item_count=Count('id'),
        total_weight=Coalesce(Sum('weight'), 0),
        total_sale_price=Coalesce(Sum(F('weight') * F('purity_price'), 
                                      output_field=DecimalField(max_digits=12, decimal_places=2)), 0),
    )
    Sales.objects.filter(id=sale_id).update(**agg)

@receiver(pre_save, sender=SaleItem)
def _capture_old_sale(sender, instance, **kwargs):
    #If updating an existing SaleItem from one sales to another, 
    #capture the old sale_id, to fix the "move" case
    if instance.pk:
        old = sender.objects.only('sale_id').get(pk=instance.pk)
        instance._old_sale_id = old.sale_id

@receiver(post_save, sender=SaleItem)
def _saleitem_saved(sender, instance, created, **kwargs):
    old_id = getattr(instance, '_old_sale_id', instance.sale_id)
    new_id = instance.sale_id

    def do():
        if old_id != new_id:
            _recompute_sales_aggregates(old_id)
        _recompute_sales_aggregates(new_id)
    transaction.on_commit(do)


@receiver(post_save, sender=SalePayment)
def mirror_refund_to_expense(sender, instance: SalePayment, created, raw=False, **kwargs):
    if raw or instance.kind != PaymentKind.REFUND:
        return
    def upsert():
        cat = ExpenseCategory.REFUND_RST if hasattr(instance.sale, "rst_details") else ExpenseCategory.REFUND_ORDER
        biz_date = getattr(instance.sale, "created_at", timezone.now()).date()
        Expense.objects.update_or_create(
            payment = instance,
            defaults = dict(
                business_date  = biz_date,
                category       = cat,
                description    = instance.description or "",
                amount         = instance.amount,
                payment_method = instance.method,
                sale           = instance.sale,
            )
        )

@receiver(post_delete, sender=SalePayment)
def remove_expense_if_refund_deleted(sender, instance: SalePayment, **kwargs):
    if instance.kind == PaymentKind.REFUND:
        Expense.objects.filter(payment=instance).delete()