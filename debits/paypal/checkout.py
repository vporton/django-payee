import json

import requests
from django.conf import settings
from django.http import HttpResponse

from debits.debits_base.processors import BasePaymentProcessor
from debits.paypal.models import PayPalAPI


class PayPalCheckoutCreate(BasePaymentProcessor):
    def make_purchase(self, hash, transaction):
        input = {
                'intent': 'sale',
                'payer': {
                    'payment_method': 'paypal'
                },
                'transactions': [
                    {
                        'amount': {
                            'total': '5.99',
                            'currency': 'USD'
                        }
                    }],
                'redirect_urls': {
                    'return_url': 'https://www.mysite.com',
                    'cancel_url': 'https://www.mysite.com'
                }
            }
        api = PayPalAPI()
        r = api.session.post(api.server + '/v1/payments/payment',
                             data=json.dumps(input),
                             headers={'content-type': 'application/json'})
        if r.status_code != 201:
            return HttpResponse('')  # TODO: What to do in this situation?
        output = r.json()
        return HttpResponse(json.dumps({'id': output['id']}))
        # return HttpResponse(json.dumps({'paymentID': output['id'], 'payerID': TODO}))  # FIXME: It is for payment execution
