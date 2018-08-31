import json

import requests

try:
    from html import escape  # python 3.x
except ImportError:
    from cgi import escape  # python 2.x
from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from debits.debits_base.models import logger, CannotCancelSubscription, CannotRefundSubscription


# This code only provides a subset of the possible functionality, for
# something more comprehensive see https://github.com/paypal/PayPal-Python-SDK
# To login into PayPal we use a Bearer from https://api.paypal.com/v1/oauth2/token
# with secret from https://developer.paypal.com/developer/applications
class PayPalAPI(models.Model):
    # Don't save it in the DB (use only for get_model())
    class Meta:
        managed = False

    def __init__(self):
        debug = settings.PAYPAL_DEBUG
        self.server = 'https://api.sandbox.paypal.com' if debug else 'https://api.paypal.com'
        s = requests.Session()
        s.headers.update({'Accept': 'application/json', 'Accept-Language': 'en_US'})
        r = s.post(self.server + '/v1/oauth2/token',
                   data='grant_type=client_credentials',
                   headers={'content-type': 'application/x-www-form-urlencoded'},
                   auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET))
        token = r.json()["access_token"]
        s.headers.update({'Authorization': 'Bearer '+token})
        self.session = s

    def cancel_agreement(self, agreement_id, is_upgrade=False):
        note = _("Upgrading billing plan") if is_upgrade else _("Canceling a service")
        # https://developer.paypal.com/docs/api/#agreement_cancel
        # https://developer.paypal.com/docs/api/payments.billing-agreements#agreement_cancel
        logger.debug("PayPal: now canceling agreement %s" % escape(agreement_id))
        r = self.session.post(self.server + ('/v1/payments/billing-agreements/%s/cancel' % escape(agreement_id)),
                              data='{"note": "%s"}' % note,
                              headers={'content-type': 'application/json'})
        if r.status_code < 200 or r.status_code >= 300:  # PayPal returns 204, to be sure
            # Don't include secret information into the message
            raise CannotCancelSubscription(r.json()["message"])
            # raise RuntimeError(_("Cannot cancel a billing agreement at PayPal. Please contact support:\n" + r.json()["message"]))

    def refund(self, transaction_id, sum=None, currency='USD'):
        logger.debug("PayPal: now refunding transaction %s" % escape(transaction_id))
        data = {}
        if sum is not None:
            data['amount'] = {'total': sum, 'currency': currency}
        r = self.session.post(self.server + ('/v1/payments/sale/%s/refund' % escape(transaction_id)),
                              data=json.dumps(data),
                              headers = {'content-type': 'application/json'})
        if r.status_code < 200 or r.status_code >= 300:  # PayPal returns 204, to be sure
            # Don't include secret information into the message
            raise CannotRefundSubscription(r.json()["message"])
            # raise RuntimeError(_("Cannot cancel a billing agreement at PayPal. Please contact support:\n" + r.json()["message"]))


    # It does not work with PayPal subscriptions: https://www.paypal-knowledge.com/infocenter/index?page=content&id=FAQ1987&actp=LIST
    # def agreement_is_active(self, agreement_id):
    #     r = self.session.get(self.server + ('/v1/payments/billing-agreements/%s' % escape(agreement_id)),
    #                          headers={'content-type': 'application/json'})
    #     # ...
