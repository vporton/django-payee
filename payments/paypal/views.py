from decimal import Decimal 
import datetime
import requests
from django.utils import timezone
from django.db import transaction
from django.http import HttpResponse
from django.views import View
from payments.payments_base.processors import PaymentCallback
from payments.payments_base.models import Transaction, Period, Payment, AutomaticPayment, Subscription, SubscriptionItem, logger, period_to_delta, model_from_ref
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
# says that recirring payments are available for PayPal Payments Standard

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
MONTHS = [
    'Jan', 'Feb', 'Mar', 'Apr',
    'May', 'Jun', 'Jul', 'Aug',
    'Sep', 'Oct', 'Nov', 'Dec',
]


# Internal.
# Based on https://github.com/spookylukey/django-paypal/blob/master/paypal/standard/forms.py
def parse_date(value):
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


class PayPalIPN(PaymentCallback, View):
    # See https://developer.paypal.com/docs/classic/express-checkout/integration-guide/ECRecurringPayments/
    # for all kinds of IPN for recurring payments.
    def post(self, request):
        try:
            self.do_post(request)
        except KeyError as e:
            logger.warning("PayPal IPN var %s is missing" % e)
        except AttributeError as e:  # if for example item.subscriptionitem for non-subscription item
            import traceback
            traceback.print_exc()
            # logger.warning(e)
        return HttpResponse('', content_type="text/plain")

    def do_post(self, request):
        POST = request.POST

        # 'payment_date', 'time_created' unused

        if POST['receiver_email'] == settings.PAYPAL_EMAIL:
            debug = settings.PAYPAL_DEBUG
            url = 'https://www.sandbox.paypal.com' if debug else 'https://www.paypal.com'
            r = requests.post(url + '/cgi-bin/webscr',
                              'cmd=_notify-validate&' + request.body.decode(POST.get('charset') or request.content_params['charset']),
                              headers={'content-type': request.content_type})  # message must use the same encoding as the original
            if r.text == 'VERIFIED':
                try:
                    transaction_id = Transaction.pk_from_custom(POST['custom'])
                    self.on_transaction_complete(POST, transaction_id)
                except Transaction.DoesNotExist:
                    logger.warning("Wrong 'custom' field for a transaction")
            else:
                logger.warning("PayPal verification not passed")
        else:
            logger.warning("Wrong PayPal email")

    def on_transaction_complete(self, POST, transaction_id):
        # Crazy: Recurring payments and subscription payments are not the same.
        # 'recurring_payment_id' and 'subscr_id' are equivalent: https://thereforei.am/2012/07/03/cancelling-subscriptions-created-with-paypal-standard-via-the-express-checkout-api/
        if 'payment_status' in POST and POST['payment_status'] == 'Refunded':
            self.accept_refund(POST, transaction_id)
        elif POST['txn_type'] in ('web_accept', 'cart', 'express_checkout'):
            self.accept_regular_payment(POST, transaction_id)
        elif POST['txn_type'] == 'recurring_payment' and \
                        POST['payment_status'] == 'Completed':
            self.accept_recurring_payment(POST, transaction_id)
        elif POST['txn_type'] == 'subscr_payment' and \
                        POST['payment_status'] == 'Completed':
            self.accept_subscription_payment(POST, transaction_id)
        elif POST['txn_type'] == 'recurring_payment_profile_created':
            self.accept_recurring_signup(POST, transaction_id)
        elif POST['txn_type'] == 'subscr_signup':
            self.accept_subscription_signup(POST, transaction_id)
        elif POST['txn_type'] in ('recurring_payment_profile_cancel', 'recurring_payment_suspended'):
            self.accept_recurring_canceled(POST, transaction_id)
        elif POST['txn_type'] == 'subscr_cancel':
            self.accept_subscription_canceled(POST, transaction_id)

    def accept_refund(self, POST, transaction_id):
        try:
            transaction = Transaction.objects.get(pk=transaction_id)
            if POST['mc_currency'] == transaction.item.currency:
                transaction.payment.refund_payment()
            else:
                logger.warning("Wrong refund currency.")
        except Transaction.DoesNotExist:
            logger.warning("Transaction %d does not exist" % transaction_id)

    def accept_regular_payment(self, POST, transaction_id):
        if POST['payment_status'] == 'Completed':
            self.do_accept_regular_payment(POST, transaction_id)

    def do_accept_regular_payment(self, POST, transaction_id):
        POST = POST.dict()  # for POST.get() below
        try:
            transaction = Transaction.objects.get(pk=transaction_id)
            item = transaction.item
            if not hasattr(item, 'subscriptionitem') and \
                            Decimal(POST['mc_gross']) == item.price and \
                            Decimal(POST['shipping']) == item.shipping and \
                            POST['mc_currency'] == item.currency:
                payment = Payment.objects.create(transaction=transaction, email=POST['payer_email'])
                item.paid = True
                item.last_payment = datetime.date.today()
                self.upgrade_subscription(transaction, item)
                item.save()
                if hasattr(item, 'prolongitem'):  # don't load the object here
                    self.advance_parent(item.prolongitem)
                else:  # TODO: Remove this else?
                    self.on_payment(payment)
            else:
                logger.warning("Wrong amount or currency")
        except Transaction.DoesNotExist:
            logger.warning("Transaction %d does not exist" % transaction_id)

    @transaction.atomic
    def advance_parent(self, prolongitem):
        parent_item = SubscriptionItem.objects.select_for_update().get(pk=prolongitem.parent_id)  # must be inside transaction
        # parent.email = transaction.email
        base_date = max(datetime.date.today(), parent_item.due_payment_date)
        parent_item.set_payment_date(base_date + period_to_delta(prolongitem.prolong))
        parent_item.save()

    def accept_recurring_payment(self, POST, transaction_id):
        try:
            self.do_accept_recurring_payment(POST, transaction_id)
        except Transaction.DoesNotExist:
            logger.warning("Transaction %d does not exist" % transaction_id)

    def do_accept_recurring_payment(self, POST, transaction_id):
        # transaction = Transaction.objects.select_for_update().get(pk=transaction_id)  # only inside transaction
        transaction = Transaction.objects.get(pk=transaction_id)
        item = transaction.item
        if hasattr(item, 'subscriptionitem') and \
                        Decimal(POST['amount_per_cycle']) == item.price + item.shipping and \
                        POST['payment_cycle'] in self.pp_payment_cycles(item.subscriptionitem):
            subscription_reference = POST['recurring_payment_id']
            subscription = self.do_create_subscription(transaction, item.subscriptionitem, subscription_reference, POST['payer_email'])
            payment = AutomaticPayment.objects.create(transaction=transaction,
                                                      email=POST['payer_email'])
            self.do_subscription_or_recurring_payment(transaction, POST)
            self.on_payment(payment)
        else:
            logger.warning("Wrong recurring payment data")

    def accept_subscription_payment(self, POST, transaction_id):
        try:
            self.do_accept_subscription_payment(POST, transaction_id)
        except Transaction.DoesNotExist:
            logger.warning("Transaction %d does not exist" % transaction_id)

    @transaction.atomic
    def do_create_subscription(self, transaction, subscriptionitem, ref, email):
        print("active_subscription:", subscriptionitem.active_subscription,
              "subscription_reference:", subscriptionitem.active_subscription.subscription_reference if subscriptionitem.active_subscription else "none",
              "ref:", ref)
        # FIXME: If the old subscription is yet present (during upgrade), the new one is not assigned
        if subscriptionitem.active_subscription and \
                        subscriptionitem.active_subscription.subscription_reference == ref:
            return subscriptionitem.active_subscription
        else:
            subscriptionitem.active_subscription = Subscription.objects.create(transaction=transaction,
                                                                               subscription_reference=ref,
                                                                               email=email)
            subscriptionitem.save()
            return subscriptionitem.active_subscription

    def do_accept_subscription_payment(self, POST, transaction_id):
        # transaction = Transaction.objects.select_for_update().get(pk=transaction_id)  # only inside transaction
        transaction = Transaction.objects.get(pk=transaction_id)
        item = transaction.item
        if hasattr(item, 'subscriptionitem') and \
                        Decimal(POST['mc_gross']) == item.price + item.shipping and \
                        POST['mc_currency'] == item.currency:
            subscription_reference = POST['subscr_id']
            subscription = self.do_create_subscription(transaction, item.subscriptionitem, subscription_reference, POST['payer_email'])
            payment = AutomaticPayment.objects.create(transaction=transaction,
                                                      email=POST['payer_email'])
            self.do_subscription_or_recurring_payment(transaction, POST)
            self.on_payment(payment)
        else:
            logger.warning("Wrong subscription payment data")

    def do_subscription_or_recurring_payment(self, transaction, POST):
        # transaction.processor = PaymentProcessor.objects.get(pk=PAYMENT_PROCESSOR_PAYPAL)
        item = transaction.item
        subscription_item = item.subscriptionitem
        subscription_item.trial = False
        date = subscription_item.due_payment_date
        while date <= datetime.date.today():
            date += period_to_delta(subscription_item.payment_period)
            subscription_item.set_payment_date(date)
            subscription_item.last_payment = datetime.date.today()
            subscription_item.reminders_sent = 0
        subscription_item.save()

    def do_subscription_or_recurring_created(self, transaction, POST):
        # transaction.processor = PaymentProcessor.objects.get(pk=PAYMENT_PROCESSOR_PAYPAL)
        item = transaction.item
        subscription_item = item.subscriptionitem
        subscription_item.trial = False
        subscription_item.save()
        self.upgrade_subscription(transaction, item)

    def accept_subscription_signup(self, POST, transaction_id):
        try:
            transaction = Transaction.objects.get(pk=transaction_id)
            item = transaction.item
            subscription_item = item.subscriptionitem
            letter = {
                Period.UNIT_DAYS: 'D',
                Period.UNIT_WEEKS: 'W',
                Period.UNIT_MONTHS: 'M',
                Period.UNIT_YEARS: 'Y',
            }[subscription_item.payment_period.unit]
            if hasattr(item, 'subscriptionitem') and \
                            Decimal(POST['amount3']) == item.price + item.shipping and \
                            POST['period3'] == str(subscription_item.payment_period.count) + ' ' + letter and \
                            POST['mc_currency'] == item.currency:
                subscription = self.do_create_subscription(transaction, item.subscriptionitem, POST['subscr_id'], POST['payer_email'])
                self.do_subscription_or_recurring_created(transaction, POST)
                self.on_subscription_created(POST, subscription)
            else:
                logger.warning("Wrong subscription signup data")
        except Transaction.DoesNotExist:
            logger.warning("Transaction %d does not exist" % transaction_id)

    def accept_recurring_signup(self, POST, transaction_id):
        try:
            transaction = Transaction.objects.get(pk=transaction_id)
            item = transaction.item
            if hasattr(item, 'subscriptionitem') and \
                            'period1' not in POST and 'period2' not in POST and \
                            Decimal(POST['mc_amount3']) == item.price + item.shipping and \
                            POST['mc_currency'] == item.currency and \
                            POST['period3'] in self.pp_payment_cycles(transaction):
                subscription = self.do_create_subscription(transaction, item.subscriptionitem, POST['recurring_payment_id'], POST['payer_email'])
                self.do_subscription_or_recurring_created(transaction, POST)
                self.on_subscription_created(POST, subscription)
            else:
                logger.warning("Wrong recurring signup data")
        except Transaction.DoesNotExist:
            logger.warning("Transaction %d does not exist" % transaction_id)

    def accept_recurring_canceled(self, POST, transaction_id):
        try:
            transaction = Transaction.objects.get(pk=transaction_id)
            transaction.item.subscriptionitem.cancel_subscription()
            self.on_subscription_canceled(POST, transaction.item.subscriptionitem)
        except Transaction.DoesNotExist:
            pass

    def accept_subscription_canceled(self, POST, transaction_id):
        try:
            transaction = Transaction.objects.get(pk=transaction_id)
            transaction.item.subscriptionitem.cancel_subscription()
            self.on_subscription_canceled(POST, transaction.item.subscriptionitem)
        except Transaction.DoesNotExist:
            pass

    # Can be called from both subscription IPN and payment IPN
    @transaction.atomic
    def upgrade_subscription(self, transaction, item):
        if item.old_subscription:
            klass = model_from_ref(item.old_subscription.transaction.processor.api)
            api = klass()
            api.cancel_agreement(item.old_subscription.subscription_reference, is_upgrade=True)
            # self.on_upgrade_subscription(transaction, item.old_subscription)  # TODO: Needed?
            item.old_subscription = None
            item.save()

    # Ugh, PayPal
    def pp_payment_cycles(self, item):
        first_tmpl = {
            Period.UNIT_DAYS: 'every %d Days',
            Period.UNIT_WEEKS: 'every %d Weeks',
            Period.UNIT_MONTHS: 'every %d Months',
            Period.UNIT_YEARS: 'every %d Years',
        }[item.payment_period.unit]
        first = first_tmpl % item.payment_period.count
        if item.payment_period.count == 1:
            second = {
                Period.UNIT_DAYS: 'Daily',
                Period.UNIT_WEEKS: 'Weekly',
                Period.UNIT_MONTHS: 'Monthly',
                Period.UNIT_YEARS: 'Yearly',
            }[item.payment_period.unit]
            return (first, second)
        else:
            return (first,)
