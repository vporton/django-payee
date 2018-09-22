import abc
import datetime
from django.urls import reverse
from debits.debits_base.processors import BasePaymentProcessor
from debits.debits_base.base import Period
from debits.debits_base.models import BaseTransaction
from django.conf import settings


# TODO:
# https://developer.paypal.com/docs/classic/express-checkout/integration-guide/ECRecurringPayments/
# You can increase the profile amount by only 20% in each 180-day interval after you create the profile.

class PayPalForm(BasePaymentProcessor):
    """Base class for processing submit of a PayPal form."""
    @classmethod
    def ipn_url(cls):
        return settings.IPN_HOST + reverse(cls.ipn_name())

    @abc.abstractclassmethod
    def ipn_name(cls):
        """Django view name for PayPal IPN."""
        pass

    def amend_hash_new_purchase(self, transaction, hash):
        # https://developer.paypal.com/docs/classic/paypal-payments-standard/integration-guide/Appx_websitestandard_htmlvariables/

        cart = hash.pop('arcamens_cart', False)

        items = self.init_items(transaction)
        if transaction.item.is_subscription():
            self.make_subscription(items, transaction, transaction.item)
        else:
            self.make_regular(items, transaction, transaction.item, cart)

        items.update(hash)
        items['bn'] = 'Arcamens_SP_EC'  # we don't want this token be changed without changing the code
        return items

    def init_items(self, transaction):
        debug = settings.PAYPAL_DEBUG
        url = 'https://www.sandbox.paypal.com' if debug else 'https://www.paypal.com'
        return {'business': settings.PAYPAL_ID,
                'arcamens_action': url + "/cgi-bin/webscr",
                'cmd': "_xclick-subscriptions" if transaction.item.is_subscription() else "_xclick",
                'notify_url': self.ipn_url(),
                'custom': BaseTransaction.custom_from_pk(transaction.pk),
                'invoice': transaction.invoice_id()}

    def make_subscription(self, items, transaction, item):
        """Internal."""
        items['item_name'] = self.product_name(item)
        items['src'] = 1

        unit_map = {Period.UNIT_DAYS: 'D',
                    Period.UNIT_WEEKS: 'W',
                    Period.UNIT_MONTHS: 'M',
                    Period.UNIT_YEARS: 'Y'}
        if item.trial_period.count > 0:
            items['a1'] = 0
            items['p1'] = item.trial_period.count
            items['t1'] = unit_map[item.trial_period.unit]
        items['a3'] = item.price + item.shipping
        items['p3'] = item.payment_period.count
        items['t3'] = unit_map[item.payment_period.unit]

    def make_regular(self, items, transaction, item, cart):
        """Internal."""
        if cart:
            items['item_name_1'] = self.product_name(item)
            items['amount_1'] = item.price
            items['shipping_1'] = item.shipping
            items['quantity_1'] = item.product_qty
            items['upload'] = 1
        else:
            items['item_name'] = self.product_name(item)[0:127]
            items['amount'] = item.price
            items['shipping'] = item.shipping
            items['quantity'] = item.product_qty

    def subscription_allowed_date(self, item):
        return max(datetime.date.today(),
                   item.due_payment_date - datetime.timedelta(days=89))  # intentionally one day added to be sure

# TODO: Support Express Checkout
# https://developer.paypal.com/docs/classic/products/express-checkout/
