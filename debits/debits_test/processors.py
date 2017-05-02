from django.shortcuts import render
from debits.paypal.form import PayPalForm

class MyPayPalForm(PayPalForm):
    def __init__(self, request):
        self.request = request

    @classmethod
    def ipn_name(cls):
        return 'paypal-ipn'
