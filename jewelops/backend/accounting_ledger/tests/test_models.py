import pytest
from decimal import Decimal
from datetime import date
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from accounting_ledger.models import (
    Sales, SaleItem, SalePayment, GoldPayment, RST, RSTItem, RSTVoided,
    Order, Expense, PaymentMethod, PaymentKind, ExpenseCategory
)


@pytest.mark.django_db
class TestSales:
    """Test Sales model functionality"""
    
    def test_sales_creation(self, sample_sale):
        """Test basic sales creation"""
        assert sample_sale.business_date == date.today()
        assert sample_sale.invoice_number == 12345
        assert sample_sale.customer_name == "John Doe"
        assert sample_sale.sold_by == "Rahman"
        assert sample_sale.item_count == 0
        assert sample_sale.total_weight == Decimal('0')
        assert sample_sale.total_sale_price == Decimal('0')
        assert sample_sale.created_at is not None

    def test_sales_string_representation(self, sample_sale):
        """Test string representation"""
        expected = f"Sale #{sample_sale.invoice_number} - {sample_sale.customer_name}"
        # Note: Add __str__ method to Sales model if needed
        
    def test_is_rst_property(self, sample_sale, sample_rst):
        """Test is_rst property"""
        assert not sample_sale.is_rst  # Initially false
        # After creating RST, it should be true
        new_rst = RST.objects.create(sale=sample_sale, rst_adv=Decimal('100.00'))
        sample_sale.refresh_from_db()
        assert sample_rst.sale.is_rst
        assert sample_sale.is_rst

    def test_is_order_property(self, sample_sale, sample_order):
        """Test is_order property"""
        # assert not sample_sale.is_order  # Initially false
        # # After creating Order, it should be true
        # sample_sale.refresh_from_db()
        assert sample_sale.is_order

    def test_sales_with_totals(self, sample_sale_with_totals):
        """Test sales with calculated totals"""
        assert sample_sale_with_totals.item_count == 2
        assert sample_sale_with_totals.total_weight == Decimal('10.50')
        assert sample_sale_with_totals.total_sale_price == Decimal('1000.00')


@pytest.mark.django_db
class TestSalePayment:
    """Test SalePayment model functionality"""
    
    def test_sale_payment_creation(self, sample_sale_payment):
        """Test basic sale payment creation"""
        assert sample_sale_payment.method == PaymentMethod.CASH
        assert sample_sale_payment.amount == Decimal('500.00')
        assert sample_sale_payment.description == "Cash payment"
        assert sample_sale_payment.kind == PaymentKind.PAYMENT

    def test_payment_methods(self, sample_sale):
        """Test all payment methods"""
        for method_code, method_name in PaymentMethod.choices:
            payment = SalePayment.objects.create(
                sale=sample_sale,
                method=method_code,
                amount=Decimal('100.00')
            )
            assert payment.method == method_code

    def test_payment_kinds(self, sample_sale):
        """Test payment and refund kinds"""
        payment = SalePayment.objects.create(
            sale=sample_sale,
            method=PaymentMethod.CASH,
            amount=Decimal('100.00'),
            kind=PaymentKind.PAYMENT
        )
        assert payment.kind == PaymentKind.PAYMENT

        refund = SalePayment.objects.create(
            sale=sample_sale,
            method=PaymentMethod.CASH,
            amount=Decimal('-50.00'),
            kind=PaymentKind.REFUND
        )
        assert refund.kind == PaymentKind.REFUND
        assert refund.amount == Decimal('-50.00')

    def test_sale_payment_relationship(self, sample_sale):
        """Test relationship between Sale and SalePayment"""
        payment1 = SalePayment.objects.create(
            sale=sample_sale,
            method=PaymentMethod.CASH,
            amount=Decimal('300.00')
        )
        payment2 = SalePayment.objects.create(
            sale=sample_sale,
            method=PaymentMethod.CARD,
            amount=Decimal('200.00')
        )
        
        assert sample_sale.payments.count() == 2
        assert payment1 in sample_sale.payments.all()
        assert payment2 in sample_sale.payments.all()


@pytest.mark.django_db
class TestGoldPayment:
    """Test GoldPayment model functionality"""
    
    def test_gold_payment_creation(self, sample_gold_payment):
        """Test gold payment creation"""
        assert sample_gold_payment.weight == Decimal('10.00')
        assert sample_gold_payment.purity == "22K"
        assert sample_gold_payment.payment.method == PaymentMethod.GOLD

    def test_gold_payment_validation_success(self, sample_sale):
        """Test successful gold payment validation"""
        sale_payment = SalePayment.objects.create(
            sale=sample_sale,
            method=PaymentMethod.GOLD,
            amount=Decimal('1000.00')
        )
        gold_payment = GoldPayment(
            payment=sale_payment,
            weight=Decimal('5.00'),
            purity="18K"
        )
        # Should not raise ValidationError
        gold_payment.clean()

    def test_gold_payment_validation_failure(self, sample_sale):
        """Test gold payment validation with wrong payment method"""
        sale_payment = SalePayment.objects.create(
            sale=sample_sale,
            method=PaymentMethod.CASH,  # Wrong method
            amount=Decimal('1000.00')
        )
        gold_payment = GoldPayment(
            payment=sale_payment,
            weight=Decimal('5.00'),
            purity="18K"
        )
        
        with pytest.raises(ValidationError):
            gold_payment.clean()


@pytest.mark.django_db
class TestSaleItem:
    """Test SaleItem model functionality"""
    
    def test_sale_item_creation(self, sample_sale):
        """Test basic sale item creation"""
        item = SaleItem.objects.create(
            sale=sample_sale,
            purity="22K",
            method=PaymentMethod.CASH,
            code=1,
            weight=Decimal('5.50'),
            purity_price=Decimal('5000.00'),
            description="Gold necklace"
        )
        
        assert item.sale == sample_sale
        assert item.purity == "22K"
        assert item.method == PaymentMethod.CASH
        assert item.code == 1
        assert item.weight == Decimal('5.50')
        assert item.purity_price == Decimal('5000.00')
        assert item.description == "Gold necklace"

    def test_sale_item_nullable_fields(self, sample_sale):
        """Test sale item with nullable fields (for orders)"""
        item = SaleItem.objects.create(
            sale=sample_sale,
            purity="22K",
            method=PaymentMethod.CASH,
            description="Order item without weight/code"
        )
        
        assert item.code is None
        assert item.weight is None
        assert item.purity_price is None

    def test_unique_constraint_violation_globally(self, sample_sale):
        """Test unique constraint prevents duplicate codes globally"""
        another_sale = Sales.objects.create(
            business_date=date.today(),
            invoice_number=99999,
            customer_name="Another Customer",
            sold_by="Sales Person"
        )
        
        # Create first item with code 1
        SaleItem.objects.create(
            sale=sample_sale,
            purity="22K",
            method=PaymentMethod.CASH,
            code=1,
            description="Item 1 for sale 1"
        )
        
        # Same code in different sale should FAIL (global uniqueness)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SaleItem.objects.create(
                    sale=another_sale,  # Different sale
                    purity="18K",
                    method=PaymentMethod.CARD,
                    code=1,  # Same code - should fail globally
                    description="Item 1 for sale 2"
                )
        
        # # This should work - different code
        # SaleItem.objects.create(
        #     sale=sample_sale,
        #     purity="22K",
        #     method=PaymentMethod.CASH,
        #     code=2,  # Different code
        #     description="Second item"
        # )

    def test_unique_constraint_allows_null_codes(self, sample_sale):
        """Test unique constraint allows multiple null codes"""
        # Multiple items with null codes should be allowed
        SaleItem.objects.create(
            sale=sample_sale,
            purity="22K",
            method=PaymentMethod.CASH,
            code=None,
            description="Order item 1"
        )
        SaleItem.objects.create(
            sale=sample_sale,
            purity="18K",
            method=PaymentMethod.CARD,
            code=None,
            description="Order item 2"
        )
        # Should not raise IntegrityError


@pytest.mark.django_db
class TestRST:
    """Test RST model functionality"""
    
    def test_rst_creation(self, sample_rst):
        """Test RST creation"""
        assert sample_rst.rst_adv == Decimal('500.00')
        assert sample_rst.rst_due == Decimal('1500.00')
        assert sample_rst.rst_final_price == Decimal('2000.00')
        assert sample_rst.delivery_date == date.today()

    def test_rst_number_property(self, sample_rst):
        """Test RST number property"""
        assert sample_rst.number == sample_rst.sale.invoice_number

    def test_rst_nullable_fields(self, sample_sale):
        """Test RST with nullable fields"""
        rst = RST.objects.create(sale=sample_sale)
        assert rst.rst_adv is None
        assert rst.rst_due is None
        assert rst.rst_final_price is None
        assert rst.delivery_date is None


@pytest.mark.django_db
class TestRSTItem:
    """Test RSTItem model functionality"""
    
    def test_rst_item_creation(self, sample_rst):
        """Test RST item creation"""
        rst_item = RSTItem.objects.create(
            rst=sample_rst,
            code=1,
            purity="22K"
        )
        
        assert rst_item.rst == sample_rst
        assert rst_item.code == 1
        assert rst_item.purity == "22K"

    def test_rst_item_unique_constraint(self, sample_rst):
        """Test unique constraint for RST items"""
        RSTItem.objects.create(rst=sample_rst, code=1, purity="22K")
        
        # Duplicate code in same RST should fail
        with pytest.raises(IntegrityError):
            RSTItem.objects.create(rst=sample_rst, code=1, purity="18K")


@pytest.mark.django_db
class TestRSTVoided:
    """Test RSTVoided model functionality"""
    
    def test_rst_voided_creation(self, sample_rst):
        """Test RST voided creation"""
        voided = RSTVoided.objects.create(rst=sample_rst)
        assert voided.rst == sample_rst
        assert voided.voided_at is not None


@pytest.mark.django_db
class TestOrder:
    """Test Order model functionality"""
    
    def test_order_creation(self, sample_order):
        """Test order creation"""
        assert sample_order.number == "12345"
        assert sample_order.assigned_to == "Worker A"
        assert sample_order.is_completed is False
        assert sample_order.delivery_date == date.today()

    def test_order_unique_number(self, sample_sale):
        """Test order number uniqueness"""
        Order.objects.create(
            sale=sample_sale,
            number="UNIQUE-001",
            assigned_to="Worker A"
        )
        
        another_sale = Sales.objects.create(
            business_date=date.today(),
            invoice_number=99999,
            customer_name="Another Customer",
            sold_by="Sales Person"
        )
        
        # Duplicate number should fail
        with pytest.raises(ValidationError) as exc_info:
            Order.objects.create(
                sale=another_sale,
                number="UNIQUE-001",
                assigned_to="Worker B"
            )
        assert 'number' in exc_info.value.message_dict
        assert 'Order with this Number already exists.' in str(exc_info.value.message_dict['number'])

    def test_order_completion_validation_no_items(self, sample_order):
        """Test order completion validation fails with no items"""
        sample_order.is_completed = True
        
        with pytest.raises(ValidationError) as exc_info:
            sample_order.clean()
        assert "Cannot complete an order with no items" in str(exc_info.value)

    def test_order_completion_validation_invalid_items(self, sample_order):
        """Test order completion validation fails with invalid items"""
        # Add item without required fields
        SaleItem.objects.create(
            sale=sample_order.sale,
            purity="22K",
            method=PaymentMethod.CASH,
            description="Incomplete item"
            # Missing code, weight, purity_price
        )
        
        sample_order.is_completed = True
        
        with pytest.raises(ValidationError) as exc_info:
            sample_order.clean()
        assert "All items must have code, positive weight, and price" in str(exc_info.value)

    def test_order_completion_validation_success(self, sample_order):
        """Test successful order completion validation"""
        # Add valid item
        SaleItem.objects.create(
            sale=sample_order.sale,
            purity="22K",
            method=PaymentMethod.CASH,
            code=1,
            weight=Decimal('5.00'),
            purity_price=Decimal('5000.00'),
            description="Complete item"
        )
        
        sample_order.is_completed = True
        # Should not raise ValidationError
        sample_order.clean()

    def test_order_save_calls_clean(self, sample_order):
        """Test that save() method calls clean()"""
        sample_order.is_completed = True
        
        # Should raise ValidationError from clean() method
        with pytest.raises(ValidationError):
            sample_order.save()


@pytest.mark.django_db
class TestExpense:
    """Test Expense model functionality"""
    
    def test_expense_creation(self):
        """Test basic expense creation"""
        expense = Expense.objects.create(
            business_date=date.today(),
            category=ExpenseCategory.OTHER,
            description="Office supplies",
            amount=Decimal('150.00'),
            payment_method=PaymentMethod.CASH
        )
        
        assert expense.business_date == date.today()
        assert expense.category == ExpenseCategory.OTHER
        assert expense.description == "Office supplies"
        assert expense.amount == Decimal('150.00')
        assert expense.payment_method == PaymentMethod.CASH
        assert expense.created_at is not None

    def test_expense_categories(self):
        """Test all expense categories"""
        for category_code, category_name in ExpenseCategory.choices:
            expense = Expense.objects.create(
                business_date=date.today(),
                category=category_code,
                amount=Decimal('100.00'),
                payment_method=PaymentMethod.CASH
            )
            assert expense.category == category_code

    def test_expense_with_sale_reference(self, sample_sale, sample_sale_payment):
        """Test expense with sale and payment references"""
        expense = Expense.objects.create(
            business_date=date.today(),
            category=ExpenseCategory.REFUND_ORDER,
            description="Refund for order",
            amount=Decimal('500.00'),
            payment_method=PaymentMethod.CASH,
            sale=sample_sale,
            payment=sample_sale_payment
        )
        
        assert expense.sale == sample_sale
        assert expense.payment == sample_sale_payment

    def test_expense_nullable_references(self):
        """Test expense with null sale and payment references"""
        expense = Expense.objects.create(
            business_date=date.today(),
            category=ExpenseCategory.OTHER,
            amount=Decimal('100.00'),
            payment_method=PaymentMethod.CASH
        )
        
        assert expense.sale is None
        assert expense.payment is None


@pytest.mark.django_db
class TestEnumChoices:
    """Test enum choices functionality"""
    
    def test_payment_method_choices(self):
        """Test PaymentMethod choices"""
        expected_choices = [
            ('CASH', 'Cash'),
            ('CARD', 'Card'),
            ('GOLD', 'Gold'),
            ('RST', 'RST Booking'),
        ]
        assert PaymentMethod.choices == expected_choices

    def test_payment_kind_choices(self):
        """Test PaymentKind choices"""
        expected_choices = [
            ('PAYMENT', 'Payment'),
            ('REFUND', 'Refund'),
        ]
        assert PaymentKind.choices == expected_choices

    def test_expense_category_choices(self):
        """Test ExpenseCategory choices"""
        expected_choices = [
            ('REFUND_ORDER', 'Refund – Order'),
            ('REFUND_RST', 'Refund – RST'),
            ('OTHER', 'Other'),
        ]
        assert ExpenseCategory.choices == expected_choices

