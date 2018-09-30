from django.shortcuts import render
from debits.paypal.form import PayPalForm
from debits.debits_base.models import ProlongPurchase

class MyPayPalForm(PayPalForm):
    """A mixin result."""

    def __init__(self, request):
        self.request = request

    @classmethod
    def ipn_name(cls):
        return 'paypal-ipn'

    def product_name(self, purchase):
        """What "product" PayPal shows for the purchase."""
        if isinstance(purchase, ProlongPurchase):
            purchase = purchase.prolonged
        return purchase.item.product.name + ': ' + purchase.mypurchase.plan.name
