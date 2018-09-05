from django.shortcuts import render
from debits.paypal.form import PayPalForm
from debits.debits_base.models import ProlongItem

class MyPayPalForm(PayPalForm):
    def __init__(self, request):
        self.request = request

    @classmethod
    def ipn_name(cls):
        return 'paypal-ipn'

    def product_name(self, item):
        if isinstance(item, ProlongItem):
            item = item.parent
        return item.product.name + ': ' + item.purchase.plan.name
