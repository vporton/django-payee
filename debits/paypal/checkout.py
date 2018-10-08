import datetime
import json

import requests
from django.conf import settings
from django.http import HttpResponse

from debits.debits_base.processors import BasePaymentProcessor
from debits.paypal.models import PayPalAPI


class PayPalCheckoutCreate(BasePaymentProcessor):
    def make_purchase(self, transaction):
        if hasattr(transaction, 'subscriptiontransaction'):
            self.make_subscription_purchase(transaction)
        else:
            self.make_regular_purchase(transaction)

    def make_regular_purchase(self, transaction):
        transactions = []
        for subpurchase in transaction.purchase.as_iter():
            subitem = subpurchase.item
            transactions.append({'amount': {
                                     'total': str(subitem.price + subpurchase.shipping + subpurchase.tax),
                                     'currency': subitem.currency,
                                     'details': {'subtotal': str(subitem.price),
                                                 'shipping': str(subpurchase.shipping),
                                                 'tax': str(subpurchase.tax)},
                                 },
                                 'description': self.product_name(subpurchase)[0:127]})
        input = {
            'intent': 'sale',
            'payer': {
                'payment_method': 'paypal'
            },
            'transactions': transactions,
        }
        input.update(self.hash)
        api = PayPalAPI()
        r = api.session.post(api.server + '/v1/payments/payment',
                             data=json.dumps(input),
                             headers={'Content-Type': 'application/json',
                                      'PayPal-Request-Id': transaction.invoice_id()})  # TODO: Or consider using invoice_number for every transaction?
        #print(r.content)
        if r.status_code != 201:
            return HttpResponse('')  # TODO: What to do in this situation?
        output = r.json()
        return HttpResponse(json.dumps({'id': output['id']}))
        # return HttpResponse(json.dumps({'paymentID': output['id'], 'payerID': TODO}))  # FIXME: It is for payment execution

    def make_subscription_purchase(self, transaction):
        pass  # TODO

    # FIXME: 1. Correct here? 2. Duplicate with form.py
    def subscription_allowed_date(self, purchase):
        return max(datetime.date.today(),
                   purchase.due_payment_date - datetime.timedelta(days=89))  # intentionally one day added to be sure
