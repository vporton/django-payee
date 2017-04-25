import requests
from html import escape
from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from payments.payments_base.models import logger


# This is a quick hack. For serious work use https://github.com/paypal/PayPal-Python-SDK instead.
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
        # We should not raise an exception, because canceling an agreement already manually canceled by a customer
        # should not break our IPN.
        if r.status_code < 200 or r.status_code >= 300:  # PayPal returns 204, to be sure
            # Don't include secret information into the message
            print(_("Cannot cancel billing agreement %s at PayPal. Please contact support:\n" % escape(agreement_id) + r.json()["message"]))
            # raise RuntimeError(_("Cannot cancel a billing agreement at PayPal. Please contact support:\n" + r.json()["message"]))
