import factory
from factory.django import DjangoModelFactory
from decimal import Decimal
from datetime import date
from accounting_ledger.models import (
    Sales, SaleItem, SalePayment, GoldPayment, RST, Order, Expense,
    PaymentMethod, PaymentKind, ExpenseCategory
)


class SalesFactory(DjangoModelFactory):
    class Meta:
        model = Sales

    business_date = factory.LazyFunction(date.today)
    invoice_number = factory.Sequence(lambda n: 10000 + n)
    customer_name = factory.Faker('name')
    sold_by = factory.Faker('first_name')
    item_count = 0
    total_weight = Decimal('0.00')
    total_sale_price = Decimal('0.00')


class SalePaymentFactory(DjangoModelFactory):
    class Meta:
        model = SalePayment

    sale = factory.SubFactory(SalesFactory)
    method = PaymentMethod.CASH
    amount = factory.Faker('pydecimal', left_digits=4, right_digits=2, positive=True)
    kind = PaymentKind.PAYMENT


class SaleItemFactory(DjangoModelFactory):
    class Meta:
        model = SaleItem

    sale = factory.SubFactory(SalesFactory)
    purity = factory.Faker('random_element', elements=['22K', '18K', '14K', '10K'])
    method = factory.Faker('random_element', elements=[choice[0] for choice in PaymentMethod.choices])
    code = factory.Sequence(lambda n: n)
    weight = factory.Faker('pydecimal', left_digits=2, right_digits=2, positive=True)
    purity_price = factory.Faker('pydecimal', left_digits=4, right_digits=2, positive=True)
    description = factory.Faker('sentence')


class RSTFactory(DjangoModelFactory):
    class Meta:
        model = RST

    sale = factory.SubFactory(SalesFactory)
    rst_adv = factory.Faker('pydecimal', left_digits=4, right_digits=2, positive=True)
    rst_due = factory.Faker('pydecimal', left_digits=4, right_digits=2, positive=True)
    rst_final_price = factory.LazyAttribute(
        lambda obj: (obj.rst_adv or Decimal('0')) + (obj.rst_due or Decimal('0'))
    )
    delivery_date = factory.Faker('future_date')


class OrderFactory(DjangoModelFactory):
    class Meta:
        model = Order

    sale = factory.SubFactory(SalesFactory)
    number = factory.Sequence(lambda n: f"ORD-{10000 + n}")
    assigned_to = factory.Faker('first_name')
    is_completed = False
    delivery_date = factory.Faker('future_date')


class ExpenseFactory(DjangoModelFactory):
    class Meta:
        model = Expense

    business_date = factory.LazyFunction(date.today)
    category = ExpenseCategory.OTHER
    description = factory.Faker('sentence')
    amount = factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    payment_method = PaymentMethod.CASH