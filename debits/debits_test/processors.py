from django.shortcuts import render

from debits.debits_base.processors import BasePaymentProcessor
from debits.paypal.checkout import PayPalCheckoutCreate
from debits.paypal.form import PayPalForm
from debits.debits_base.models import ProlongPurchase


class MyBaseFormMixin(BasePaymentProcessor):
    def product_name(self, purchase):
        """What "product" PayPal shows for the purchase."""
        if isinstance(purchase, ProlongPurchase):
            purchase = purchase.prolonged
        return purchase.item.product.name + ': ' + purchase.mypurchase.plan.name


class MyPayPalForm(PayPalForm, MyBaseFormMixin):
    """A mixin result."""

    @classmethod
    def ipn_name(cls):
        return 'paypal-ipn'


class MyPayPalCheckoutCreate(PayPalCheckoutCreate, MyBaseFormMixin):
    pass