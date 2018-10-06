import json

import requests
from django.conf import settings
from django.http import HttpResponse

from debits.debits_base.processors import BasePaymentProcessor
from debits.paypal.models import PayPalAPI


class PayPalCheckoutCreate(BasePaymentProcessor):
    # FIXME: It works only for non-subscription payments
    def make_purchase(self, hash, transaction):
        transactions = []
        for subpurchase in transaction.purchase.as_iter():
            subitem = subpurchase.item
            transactions.append({'amount': subitem.price + subitem.shipping + subitem.tax,
                                 'currency': subitem.currency,
                                 'details':{'subtotal': subitem.price, 'shipping': subitem.shipping, 'tax': subitem.tax},
                                 'description': self.product_name(subpurchase)[0:127]})
        input = {
            'intent': 'sale',  # TODO: Other modes (cannot pass through a form parameter for security reasons)
            'payer': {
                'payment_method': 'paypal'
            },
            'transactions': transactions,
            'redirect_urls': {
                'return_url': 'https://www.mysite.com',
                'cancel_url': 'https://www.mysite.com'
            }
        }
        api = PayPalAPI()
        r = api.session.post(api.server + '/v1/payments/payment',
                             data=json.dumps(input),
                             headers={'Content-Type': 'application/json',
                                      'PayPal-Request-Id': transaction.invoice_id()})  # TODO: Or consider using invoice_number for every transaction?
        if r.status_code != 201:
            return HttpResponse('')  # TODO: What to do in this situation?
        output = r.json()
        return HttpResponse(json.dumps({'id': output['id']}))
        # return HttpResponse(json.dumps({'paymentID': output['id'], 'payerID': TODO}))  # FIXME: It is for payment execution
