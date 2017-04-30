import abc
import datetime
from django.urls import reverse
from payee.payee_base.processors import BasePaymentProcessor
from payee.payee_base.models import BaseTransaction, Period
from django.conf import settings


# https://developer.paypal.com/docs/classic/express-checkout/integration-guide/ECRecurringPayments/
# You can increase the profile amount by only 20% in each 180-day interval after you create the profile.

class PayPalForm(BasePaymentProcessor):
    @classmethod
    def ipn_url(cls):
        return settings.IPN_HOST + reverse(cls.ipn_name())

    @abc.abstractclassmethod
    def ipn_name(cls):
        pass

    def amend_hash_new_purchase(self, transaction, hash):
        # https://developer.paypal.com/docs/classic/paypal-payments-standard/integration-guide/Appx_websitestandard_htmlvariables/

        cart = hash.get('arcamens_cart', False)
        if cart:
            del hash['arcamens_cart']

        debug = settings.PAYPAL_DEBUG
        url = 'https://www.sandbox.paypal.com' if debug else 'https://www.paypal.com'

        invoice_id = transaction.invoice_id()

        items = {'business': settings.PAYPAL_ID,
                 'arcamens_action': url + "/cgi-bin/webscr",
                 'cmd': "_xclick-subscriptions" if is_subscription else "_xclick",
                 'notify_url': self.ipn_url(),
                 'custom': BaseTransaction.custom_from_pk(transaction.pk),
                 'invoice': invoice_id}

        item = transaction.item

        if item.is_subscription():
            items['item_name'] = transaction.item.product.name
            items['src'] = 1

            unit_map = {Period.UNIT_DAYS: 'D',
                        Period.UNIT_WEEKS: 'W',
                        Period.UNIT_MONTHS: 'M',
                        Period.UNIT_YEARS: 'Y'}
            remaining_days = self.calculate_remaining_days(transaction)
            if remaining_days > 0:
                items['a1'] = 0
                items['p1'] = remaining_days
                items['t1'] = 'D'
            items['a3'] = item.price + item.shipping
            items['p3'] = item.payment_period.count
            items['t3'] = unit_map[item.payment_period.unit]
        else:
            if cart:
                items['item_name_1'] = item.product.name
                items['amount_1'] = item.price
                items['shipping_1'] = item.shipping
                items['quantity_1'] = item.product_qty
                items['upload'] = 1
            else:
                items['item_name'] = item.product.name
                items['amount'] = item.price
                items['shipping'] = item.shipping
                items['quantity'] = item.product_qty

        items.update(hash)
        return items

    def subscription_allowed_date(self, item):
        return max(datetime.date.today(),
                   item.due_payment_date - datetime.timedelta(days=89))  # intentionally one day added to be sure

# TODO: Support Exress Checkout
# https://developer.paypal.com/docs/classic/products/express-checkout/
