import json

import requests
from dateutil.relativedelta import relativedelta

from debits.debits_base.base import Period, period_to_delta

try:
    from html import escape  # python 3.x
except ImportError:
    from cgi import escape  # python 2.x
from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from debits.debits_base.models import logger, CannotCancelSubscription, CannotRefundSubscription


class PayPalProcessorInfo(models.Model):
    class Meta:
        """Don't save it in the DB (use only for get_model())"""
        managed = False

    def api(self):
        return PayPalAPI()

    @staticmethod
    def offset_date(date, offset):
        """Used to calculate the next recurring payment date."""
        delta = period_to_delta(offset)
        new_date = date + delta
        if offset.unit in (Period.UNIT_MONTHS, Period.UNIT_YEARS) and new_date.day != date.day:
            new_date += relativedelta(days=1)
        return new_date


class PayPalAPI(object):
    """PayPal API.

    This code only provides a subset of the possible functionality, for
    something more comprehensive see https://github.com/paypal/PayPal-Python-SDK
    To login into PayPal we use a Bearer from https://api.paypal.com/v1/oauth2/token
    with secret from https://developer.paypal.com/developer/applications"""

    def __init__(self):
        """Creates a HTTP session to access PayPal API."""
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
        """Cancels a PayPal recurring payment."""
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
        """Refunds a PayPal payment."""
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
