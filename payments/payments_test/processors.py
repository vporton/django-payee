from django.shortcuts import render
from payments.paypal.form import PayPalForm

class MyPayPalForm(PayPalForm):
    def __init__(self, request):
        self.request = request

    @classmethod
    def ipn_name(cls):
        return 'paypal-ipn'
