import traceback
from decimal import Decimal
import datetime
import requests
from django.utils import timezone
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from debits.debits_base.processors import PaymentCallback, PAYMENT_PROCESSOR_PAYPAL
from debits.debits_base.base import logger
from debits.debits_base.models import BaseTransaction, SimpleTransaction, SubscriptionTransaction, AutomaticPayment, \
    SubscriptionPurchase
from debits.debits_base.base import Period
from django.conf import settings


# https://www.angelleye.com/paypal-recurring-payments-reference-transactions-and-preapproved-payments/

# https://developer.paypal.com/docs/classic/ipn/integration-guide/IPNIntro/
# https://developer.paypal.com/docs/classic/ipn/integration-guide/IPNandPDTVariables/

# Examples of IPN for recurring payments:
# https://www.angelleye.com/paypal-recurring-payments-ipn-samples/
# https://gist.github.com/thenbrent/3037967

# How to test IPN:
# https://developer.paypal.com/docs/classic/ipn/integration-guide/IPNTesting/

# https://developer.paypal.com/docs/classic/products/recurring-payments/
# says that recurring payments are available for PayPal Payments Standard

# https://developer.paypal.com/docs/classic/express-checkout/integration-guide/ECRecurringPayments/
# for a general introduction into recurring payments in PayPal

# This is a trouble: https://developer.paypal.com/docs/classic/express-checkout/integration-guide/ECRecurringPayments/
# "For recurring payments with the Express Checkout API, PayPal does not allow certain updates, such as billing amount, within 3 days of the scheduled billing date."

# Recurring payments cannot be created for buyers in Germany or China. In this case, you can use reference transactions as an alternate solution:
# https://developer.paypal.com/docs/classic/express-checkout/integration-guide/ECReferenceTxns/


# # Internal
# def parse_date(string):
#     # Not tread safe!!
#     # old_locale = locale.getlocale(locale.LC_TIME)
#     # locale.setlocale(locale.LC_TIME, "C")
#     ret = datetime.datetime.strptime(string, '%H:%M:%S %b %d, %Y %Z')
#     # locale.setlocale(locale.LC_TIME, old_locale)
#     return ret


# Internal.
from debits.paypal.models import PayPalAPI, PayPalProcessorInfo

MONTHS = [
    'Jan', 'Feb', 'Mar', 'Apr',
    'May', 'Jun', 'Jul', 'Aug',
    'Sep', 'Oct', 'Nov', 'Dec',
]


# Based on https://github.com/spookylukey/django-paypal/blob/master/paypal/standard/forms.py
def parse_date(value):
    """Internal."""
    value = value.strip()  # needed?

    time_part, month_part, day_part, year_part, zone_part = value.split()
    month_part = month_part.strip(".")
    day_part = day_part.strip(",")
    month = MONTHS.index(month_part) + 1
    day = int(day_part)
    year = int(year_part)
    hour, minute, second = map(int, time_part.split(":"))
    dt = datetime(year, month, day, hour, minute, second)

    if zone_part in ["PDT", "PST"]:
        # PST/PDT is 'US/Pacific'
        dt = timezone.pytz.timezone('US/Pacific').localize(
            dt, is_dst=zone_part == 'PDT')
        if not settings.USE_TZ:
            dt = timezone.make_naive(dt, timezone=timezone.utc)
    return dt


# FIXME: Refund fails for coupon or gift certificates, because they support only full refunds

@method_decorator(csrf_exempt, name='dispatch')
class PayPalIPN(PaymentCallback, View):
    """This class processes all kinds of PayPal IPNs.

    All its methods are considered internal."""

    # See https://developer.paypal.com/docs/classic/express-checkout/integration-guide/ECRecurringPayments/
    # for all kinds of IPN for recurring payments.
    def post(self, request):
        try:
            self.do_post(request)
        except KeyError as e:
            logger.warning("PayPal IPN var %s is missing" % e)
        except:
            import traceback
            traceback.print_exc()
        return HttpResponse('', content_type="text/plain")

    def do_post(self, request):
        # 'payment_date', 'time_created' unused
        if request.POST['receiver_email'] == settings.PAYPAL_EMAIL:
            self.do_do_post(request.POST, request)
        else:
            logger.warning("Wrong PayPal email")

    def do_do_post(self, POST, request):
        debug = settings.PAYPAL_DEBUG
        url = 'https://www.sandbox.paypal.com' if debug else 'https://www.paypal.com'
        r = requests.post(url + '/cgi-bin/webscr',
                          'cmd=_notify-validate&' + request.body.decode(
                              POST.get('charset') or request.content_params['charset']),
                          headers={
                              'content-type': request.content_type})  # message must use the same encoding as the original
        if r.text == 'VERIFIED':
            self.verified_post(POST, request)
        else:
            logger.warning("PayPal verification not passed")

    def verified_post(self, POST, request):
        # print('custom', POST['custom'])  # Don't print sensitive data
        transaction_id = BaseTransaction.pk_from_custom(POST['custom'])
        self.on_transaction_complete(POST, transaction_id)

    def on_transaction_complete(self, POST, transaction_id):
        # Crazy: Recurring payment and subscription debits are not the same.
        # 'recurring_payment_id' and 'subscr_id' are equivalent: https://thereforei.am/2012/07/03/cancelling-subscriptions-created-with-paypal-standard-via-the-express-checkout-api/
        type_dispatch = {
            'web_accept': self.accept_regular_payment,
            'cart': self.accept_regular_payment,
            'express_checkout': self.accept_regular_payment,
            'recurring_payment': self.accept_recurring_payment,
            'subscr_payment': self.accept_subscription_payment,
            'recurring_payment_profile_created': self.accept_recurring_signup,
            'subscr_signup': self.accept_subscription_signup,
            'recurring_payment_profile_cancel': self.accept_recurring_canceled,
            'recurring_payment_suspended': self.accept_recurring_canceled,
            'subscr_cancel': self.accept_recurring_canceled
        }
        if 'payment_status' in POST and POST['payment_status'] == 'Refunded':
            self.accept_refund(POST, transaction_id)
        else:
            type_dispatch[POST['txn_type']](POST, transaction_id)

    def accept_refund(self, POST, transaction_id):
        self.do_appect_refund(POST, transaction_id)

    def do_appect_refund(self, POST, transaction_id):
        try:
            transaction = BaseTransaction.objects.get(pk=transaction_id)
        except BaseTransaction.DoesNotExist:
            traceback.print_exc()
            return
        if POST['mc_currency'] == transaction.purchase.item.currency:
            transaction.payment.refund_payment()
        else:
            logger.warning("Wrong refund currency.")

    def accept_regular_payment(self, POST, transaction_id):
        if POST['payment_status'] == 'Completed':
            self.do_accept_regular_payment(POST, transaction_id)

    def do_accept_regular_payment(self, POST, transaction_id):
        POST = POST.dict()  # for POST.get() below
        self.do_do_accept_regular_payment(POST, transaction_id)

    def do_do_accept_regular_payment(self, POST, transaction_id):
        try:
            transaction = SimpleTransaction.objects.get(pk=transaction_id)
        except BaseTransaction.DoesNotExist:
            traceback.print_exc()
            return
        if Decimal(POST['mc_gross']) == transaction.purchase.item.price and \
                        Decimal(POST['shipping']) == transaction.purchase.shipping and \
                        Decimal(POST['tax']) == transaction.purchase.tax and \
                        POST['mc_currency'] == transaction.purchase.item.currency:
            if self.auto_refund(transaction, transaction.purchase.simplepurchase.prolongpurchase.prolonged, POST):
                return HttpResponse('')
            payment = transaction.on_accept_regular_payment(POST['payer_email'])
            self.on_payment(payment)
        else:
            logger.warning("Wrong amount or currency")

    def accept_recurring_payment(self, POST, transaction_id):
        if POST['payment_status'] != 'Completed':
            return
        self.do_accept_recurring_payment(POST, transaction_id)

    def do_accept_recurring_payment(self, POST, transaction_id):
        # transaction = BaseTransaction.objects.select_for_update().get(pk=transaction_id)  # only inside transaction
        try:
            transaction = SubscriptionTransaction.objects.get(pk=transaction_id)
        except BaseTransaction.DoesNotExist:
            traceback.print_exc()
            return
        if Decimal(POST['amount_per_cycle']) == transaction.purchase.item.price + transaction.purchase.item.shipping + transaction.purchase.item.tax and \
                        POST['payment_cycle'] in self.pp_payment_cycles(transaction.purchase.item):
            self.do_do_accept_subscription_or_recurring_payment(transaction, transaction.purchase.item, POST, POST['recurring_payment_id'])
        else:
            logger.warning("Wrong recurring payment data")

    def accept_subscription_payment(self, POST, transaction_id):
        if POST['payment_status'] != 'Completed':
            return
        self.do_accept_subscription_payment(POST, transaction_id)

    def do_do_accept_subscription_or_recurring_payment(self, transaction, purchase, POST, ref):
        if self.auto_refund(transaction, purchase, POST):
            return HttpResponse('')
        purchase.subscriptionpurchase.activate_subscription(ref, POST['payer_email'], PAYMENT_PROCESSOR_PAYPAL)
        # This is already done in activate_subscription():
        payment = AutomaticPayment.objects.create(transaction=transaction,
                                                  email=POST['payer_email'],
                                                  subscription_reference=ref,
                                                  processor_id=PAYMENT_PROCESSOR_PAYPAL)
        purchase.payment = payment
        self.do_subscription_or_recurring_payment(purchase.subscriptionpurchase)  # calls save()
        self.on_payment(transaction.payment.automaticpayment)

    def do_accept_subscription_payment(self, POST, transaction_id):
        # transaction = BaseTransaction.objects.select_for_update().get(pk=transaction_id)  # only inside transaction
        try:
            transaction = SubscriptionTransaction.objects.get(pk=transaction_id)
        except BaseTransaction.DoesNotExist:
            traceback.print_exc()
            return
        purchase = transaction.purchase
        if Decimal(POST['mc_gross']) == purchase.item.price + purchase.shipping + purchase.tax and \
                        POST['mc_currency'] == purchase.item.currency:
            self.do_do_accept_subscription_or_recurring_payment(transaction, purchase, POST, POST['subscr_id'])
        else:
            logger.warning("Wrong subscription payment data")

    def do_subscription_or_recurring_payment(self, purchase):
        # transaction.processor = PaymentProcessor.objects.get(pk=PAYMENT_PROCESSOR_PAYPAL)
        purchase.trial = False
        date = purchase.due_payment_date
        if purchase.item.subscriptionitem.payment_period.count > 0:  # hack to eliminate infinite loop
            while date <= datetime.date.today():
                date = self.advance_item_date(date, purchase)
        purchase.due_payment_date = date
        purchase.save()

    def advance_item_date(self, date, purchase):
        date = PayPalProcessorInfo.offset_date(date, purchase.item.subscriptionitem.payment_period)
        purchase.set_payment_date(date)
        purchase.reminders_sent = 0
        return date

    def do_subscription_or_recurring_created(self, transaction, POST, ref):
        purchase = transaction.purchase.subscriptionpurchase
        purchase.activate_subscription(ref, POST['payer_email'], PAYMENT_PROCESSOR_PAYPAL)
        # transaction.processor = PaymentProcessor.objects.get(pk=PAYMENT_PROCESSOR_PAYPAL)
        SubscriptionPurchase.objects.filter(pk=purchase.pk).update(trial=False)
        purchase.upgrade_subscription()
        self.on_subscription_created(POST, purchase)

    def accept_subscription_signup(self, POST, transaction_id):
        self.do_accept_subscription_signup(POST, transaction_id)

    def do_accept_subscription_signup(self, POST, transaction_id):
        try:
            transaction = SubscriptionTransaction.objects.get(pk=transaction_id)
        except BaseTransaction.DoesNotExist:
            traceback.print_exc()
            return
        purchase = transaction.purchase.subscriptionpurchase
        m = {
            Period.UNIT_DAYS: 'D',
            Period.UNIT_WEEKS: 'W',
            Period.UNIT_MONTHS: 'M',
            Period.UNIT_YEARS: 'Y',
        }
        period1_right = (purchase.item.subscriptionitem.trial_period.count == 0 and 'period1' not in POST) or \
                        (purchase.item.subscriptionitem.trial_period.count != 0 and 'period1' in POST and \
                         POST['period1'] == str(purchase.item.subscriptionitem.trial_period.count)+' '+m[purchase.item.subscriptionitem.trial_period.unit])
        if period1_right and 'period2' not in POST and \
                        Decimal(POST['amount3']) == purchase.item.price and \
                        POST['period3'] == str(purchase.item.subscriptionitem.payment_period.count)+' '+m[purchase.item.subscriptionitem.payment_period.unit] and \
                        POST['mc_currency'] == purchase.item.currency:
            self.do_subscription_or_recurring_created(transaction, POST, POST['subscr_id'])
        else:
            logger.warning("Wrong subscription signup data")

    def accept_recurring_signup(self, POST, transaction_id):
        try:
            transaction = SubscriptionTransaction.objects.get(pk=transaction_id)
        except BaseTransaction.DoesNotExist:
            traceback.print_exc()
            return
        if 'period1' not in POST and 'period2' not in POST and \
                        Decimal(POST['mc_amount3']) == transaction.purchase.item.price + transaction.purchase.shipping + transaction.purchase.tax and \
                        POST['mc_currency'] == transaction.purchase.item.currency and \
                        POST['period3'] in self.pp_payment_cycles(transaction):
            self.do_subscription_or_recurring_created(transaction, POST, POST['recurring_payment_id'])
        else:
            logger.warning("Wrong recurring signup data")

    def accept_recurring_canceled(self, POST, transaction_id):
        self.do_accept_recurring_canceled(POST, transaction_id)

    def do_accept_recurring_canceled(self, POST, transaction_id):
        try:
            transaction = SubscriptionTransaction.objects.get(pk=transaction_id)
        except BaseTransaction.DoesNotExist:
            traceback.print_exc()

            return
        transaction.purchase.subscriptionpurchase.cancel_subscription()
        self.on_subscription_canceled(POST, transaction.purchase)

    def auto_refund(self, transaction, purchase, POST):
        # "purchase" is SubscriptionItem
        if self.should_auto_refund():
            api = PayPalAPI()
            # FIXME: Wrong for American Express card: https://www.paypal.com/us/selfhelp/article/How-do-I-issue-a-full-or-partial-refund-FAQ780
            amount = (transaction.purchase.item.price - Decimal(0.30)).quantize(Decimal('1.00'))
            api.refund(POST['txn_id'], str(amount))
            return True
        return False

    def should_auto_refund(self):
        return False

    # Ugh, PayPal
    def pp_payment_cycles(self, purchase):
        first_tmpl = {
            Period.UNIT_DAYS: 'every %d Days',
            Period.UNIT_WEEKS: 'every %d Weeks',
            Period.UNIT_MONTHS: 'every %d Months',
            Period.UNIT_YEARS: 'every %d Years',
        }[purchase.item.subscriptionitem.payment_period.unit]
        first = first_tmpl % purchase.item.subscriptionitem.payment_period.count
        if purchase.item.subscriptionitem.payment_period.count == 1:
            second = {
                Period.UNIT_DAYS: 'Daily',
                Period.UNIT_WEEKS: 'Weekly',
                Period.UNIT_MONTHS: 'Monthly',
                Period.UNIT_YEARS: 'Yearly',
            }[purchase.item.subscriptionitem.payment_period.unit]
            return (first, second)
        else:
            return (first,)
