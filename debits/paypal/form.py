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

        cart = hash.pop('arcamens_cart', transaction.purchase.is_aggregate)

        items = self.init_items(transaction)
        # if transaction.purchase.item.is_subscription():
        if hasattr(transaction, 'subscriptiontransaction'):
            self.make_subscription(items, transaction, transaction.purchase)
        else:
            self.make_regular(items, transaction, transaction.purchase, cart)

        items.update(hash)
        items['bn'] = 'Arcamens_SP_EC'  # we don't want this token be changed without changing the code
        return items

    def init_items(self, transaction):
        debug = settings.PAYPAL_DEBUG
        url = 'https://www.sandbox.paypal.com' if debug else 'https://www.paypal.com'
        return {'business': settings.PAYPAL_ID,
                'arcamens_action': url + "/cgi-bin/webscr",
                'cmd': "_xclick-subscriptions" if hasattr(transaction, 'subscriptiontransaction') else "_xclick",
                'notify_url': self.ipn_url(),
                'custom': BaseTransaction.custom_from_pk(transaction.pk),
                'invoice': transaction.invoice_id()}

    def make_subscription(self, items, transaction, purchase):
        """Internal."""
        items['item_name'] = self.product_name(purchase)
        items['src'] = 1

        unit_map = {Period.UNIT_DAYS: 'D',
                    Period.UNIT_WEEKS: 'W',
                    Period.UNIT_MONTHS: 'M',
                    Period.UNIT_YEARS: 'Y'}
        if purchase.item.subscriptionitem.trial_period.count > 0:
            items['a1'] = 0
            items['p1'] = purchase.item.subscriptionitem.trial_period.count
            items['t1'] = unit_map[purchase.item.subscriptionitem.trial_period.unit]
        items['a3'] = purchase.item.price + purchase.shipping + purchase.tax
        items['p3'] = purchase.item.subscriptionitem.payment_period.count
        items['t3'] = unit_map[purchase.item.subscriptionitem.payment_period.unit]

    def make_regular(self, items, transaction, purchase, cart):
        """Internal."""
        if cart:
            items['upload'] = 1
            i = 1
            for child in purchase.aggregatepurchase.childs.order_by('pk') if purchase.is_aggregate else [purchase]:
                items['item_name_' + str(i)] = self.product_name(child)
                items['amount_' + str(i)] = child.item.price
                items['shipping_' + str(i)] = child.shipping
                items['tax_' + str(i)] = child.tax
                items['quantity_' + str(i)] = child.item.product_qty
                i += 1
        else:
            items['item_name'] = self.product_name(purchase)[0:127]
            items['amount'] = purchase.item.price
            items['shipping'] = purchase.shipping
            items['tax'] = purchase.tax
            items['quantity'] = purchase.item.product_qty

    def subscription_allowed_date(self, purchase):
        return max(datetime.date.today(),
                   purchase.due_payment_date - datetime.timedelta(days=89))  # intentionally one day added to be sure

# TODO: Support Express Checkout
# https://developer.paypal.com/docs/classic/products/express-checkout/
