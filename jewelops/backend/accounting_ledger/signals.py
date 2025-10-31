from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Count, F, DecimalField, Q
from django.db.models.functions import Coalesce
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from .models import (
    Item, ItemStatus, Sales, SaleItem, SalePayment, PaymentKind,
    RST, RSTStatus, RSTItem, RSTVoided
)


# =============================================================================
# SALES AGGREGATES - Auto-update item_count, total_weight, total_sale_price
# =============================================================================

# def recompute_sales_aggregates(sale_id):
#     """
#     Recompute and update the item_count, total_weight, and total_sale_price
#     for the given Sales instance.
#     """
#     if not sale_id:
#         return
        
#     agg = SaleItem.objects.filter(sale_id=sale_id).aggregate(
#         item_count=Count('id'),
#         total_weight=Coalesce(
#             Sum('item__weight'), 
#             Decimal('0.00'),
#             output_field=DecimalField(max_digits=10, decimal_places=2)
#         ),
#         total_sale_price=Coalesce(
#             Sum(
#                 F('item__weight') * F('purity_price'),
#                 output_field=DecimalField(max_digits=10, decimal_places=2)
#             ), 
#             Decimal('0.00'),
#             output_field=DecimalField(max_digits=10, decimal_places=2)
#         ),
#     )
    
#     Sales.objects.filter(id=sale_id).update(**agg)


# @receiver(pre_save, sender=SaleItem)
# def capture_old_sale_for_saleitem(sender, instance, **kwargs):
#     """Capture old sale_id before save to handle sale changes"""
#     if instance.pk:
#         try:
#             old = sender.objects.only('sale_id').get(pk=instance.pk)
#             instance._old_sale_id = old.sale_id
#         except sender.DoesNotExist:
#             instance._old_sale_id = None


# @receiver(post_save, sender=SaleItem)
# def update_sales_aggregates_on_saleitem_save(sender, instance, created, **kwargs):
#     """Update sales aggregates when SaleItem is created/updated"""
#     old_sale_id = getattr(instance, '_old_sale_id', None)
#     new_sale_id = instance.sale_id
    
#     def update_aggregates():
#         # If item moved between sales, update both
#         if old_sale_id and old_sale_id != new_sale_id:
#             recompute_sales_aggregates(old_sale_id)
        
#         recompute_sales_aggregates(new_sale_id)
    
#     transaction.on_commit(update_aggregates)


# @receiver(post_delete, sender=SaleItem)
# def update_sales_aggregates_on_saleitem_delete(sender, instance, **kwargs):
#     """Update sales aggregates when SaleItem is deleted"""
#     def update_aggregates():
#         recompute_sales_aggregates(instance.sale_id)
    
#     transaction.on_commit(update_aggregates)


# =============================================================================
# ITEM STATUS MANAGEMENT - Auto-update Item.status based on sales/RST
# =============================================================================

@receiver(post_save, sender=SaleItem)
def update_item_status_on_sale(sender, instance, created, **kwargs):
    """Set item status to SOLD when added to a regular sale"""
    def update_status():
        # Check if this is an RST sale
        if hasattr(instance.sale, 'rst_details'):
            # RST booking - set to RST_BOOKED
            Item.objects.filter(pk=instance.item_id).update(status=ItemStatus.RST_BOOKED)
        else:
            # Regular sale - set to SOLD
            Item.objects.filter(pk=instance.item_id).update(status=ItemStatus.SOLD)
    
    transaction.on_commit(update_status)


@receiver(post_delete, sender=SaleItem)
def revert_item_status_on_sale_delete(sender, instance, **kwargs):
    """Revert item status to AVAILABLE when removed from sale"""
    def update_status():
        Item.objects.filter(pk=instance.item_id).update(status=ItemStatus.AVAILABLE)
    
    transaction.on_commit(update_status)


@receiver(post_save, sender=RSTVoided)
def revert_item_status_on_rst_void(sender, instance, created, **kwargs):
    """Revert all RST items to AVAILABLE when RST is voided"""
    if not created:
        return
    
    def update_status():
        # Get all items in this RST and set them back to AVAILABLE
        rst_item_ids = instance.rst.sale.items.values_list('item_id', flat=True)
        Item.objects.filter(pk__in=rst_item_ids).update(status=ItemStatus.AVAILABLE)
    
    transaction.on_commit(update_status)


# =============================================================================
# RST STATUS MANAGEMENT - Auto-update RST status based on payments
# =============================================================================

def calculate_rst_payment_totals(rst_id):
    """Calculate total advance and balance payments for an RST"""
    rst_payments = SalePayment.objects.filter(sale__rst_details__id=rst_id)
    
    advance_total = rst_payments.filter(
        kind=PaymentKind.RST_ADVANCE
    ).aggregate(
        total=Coalesce(Sum('amount'), Decimal('0.00'))
    )['total']
    
    balance_total = rst_payments.filter(
        kind=PaymentKind.RST_BALANCE
    ).aggregate(
        total=Coalesce(Sum('amount'), Decimal('0.00'))
    )['total']
    
    return advance_total, balance_total


def update_rst_status_and_amounts(rst_id):
    """Update RST status and payment amounts based on current payments"""
    try:
        rst = RST.objects.get(id=rst_id)
        advance_total, balance_total = calculate_rst_payment_totals(rst_id)
        
        # Calculate due amount
        total_paid = advance_total + balance_total
        rst_due = (rst.rst_final_price or Decimal('0.00')) - total_paid
        
        # Determine status
        if rst_due <= 0 and rst.rst_final_price and rst.rst_final_price > 0:
            status = RSTStatus.COMPLETED
        else:
            status = RSTStatus.BOOKED
        
        # Update RST
        RST.objects.filter(id=rst_id).update(
            rst_adv=advance_total,
            rst_due=max(rst_due, Decimal('0.00')),  # Don't allow negative due amounts
        )
        
        # Update sale status if needed (you might want a status field on Sales for RST)
        
    except RST.DoesNotExist:
        pass


@receiver(post_save, sender=SalePayment)
def update_rst_on_payment_change(sender, instance, created, **kwargs):
    """Update RST status when RST-related payments are made"""
    if instance.kind in [PaymentKind.RST_ADVANCE, PaymentKind.RST_BALANCE]:
        if hasattr(instance.sale, 'rst_details'):
            def update_rst():
                update_rst_status_and_amounts(instance.sale.rst_details.id)
            
            transaction.on_commit(update_rst)


@receiver(post_delete, sender=SalePayment)
def update_rst_on_payment_delete(sender, instance, **kwargs):
    """Update RST status when RST-related payments are deleted"""
    if instance.kind in [PaymentKind.RST_ADVANCE, PaymentKind.RST_BALANCE]:
        if hasattr(instance.sale, 'rst_details'):
            def update_rst():
                update_rst_status_and_amounts(instance.sale.rst_details.id)
            
            transaction.on_commit(update_rst)


@receiver(post_save, sender=RST)
def update_rst_on_final_price_change(sender, instance, created, **kwargs):
    """Update RST calculations when rst_final_price changes"""
    if not created:  # Only on updates
        def update_rst():
            update_rst_status_and_amounts(instance.id)
        
        transaction.on_commit(update_rst)