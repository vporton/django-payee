import abc
import hmac
import datetime

import html2text
import logging
from django.apps import apps
from django.urls import reverse
from django.db import models
from django.db.models import F
import django.db
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from composite_field import CompositeField
from django.conf import settings

from debits.debits_base.base import Period
from debits.paypal.utils import PayPalUtils

logger = logging.getLogger('debits')


class ModelRef(CompositeField):
    app_label = models.CharField(max_length=100)
    model = models.CharField(_('python model class name'), max_length=100)


# The following two functions does not work as methods, because
# CompositeField is replaced with composite_field.base.CompositeField.Proxy:

def model_from_ref(model_ref):
    return apps.get_model(model_ref.app_label, model_ref.model)


class PaymentProcessor(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=255)
    api = ModelRef()

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


# The following two functions does not work as methods, because
# CompositeField is replaced with composite_field.base.CompositeField.Proxy:

def period_to_string(period):
    hash = {e[0]: e[1] for e in Period.period_choices}
    return "%d %s" % (period.count, hash[period.unit])


class BaseTransaction(models.Model):
    """
    ONE redirect to the payment processor
    """

    # class Meta:
    #     abstract = True

    processor = models.ForeignKey(PaymentProcessor, on_delete=models.CASCADE)
    creation_date = models.DateField(auto_now_add=True)

    def __repr__(self):
        return "<BaseTransaction: %s>" % (("pk=%d" % self.pk) if self.pk else "no pk")

    @staticmethod
    def custom_from_pk(pk):
        # Secret can be known only to one who created a BaseTransaction.
        # This prevents third parties to make fake IPNs from a payment processor.
        secret = hmac.new(settings.SECRET_KEY.encode(), ('payid ' + str(pk)).encode()).hexdigest()
        return settings.PAYMENTS_REALM + ' ' + str(pk) + ' ' + secret

    @staticmethod
    def pk_from_custom(custom):
        r = custom.split(' ', 2)
        if len(r) != 3 or r[0] != settings.PAYMENTS_REALM:
            raise BaseTransaction.DoesNotExist
        try:
            pk = int(r[1])
            secret = hmac.new(settings.SECRET_KEY.encode(), ('payid ' + str(pk)).encode()).hexdigest()
            if r[2] != secret:
                raise BaseTransaction.DoesNotExist
            return pk
        except ValueError:
            raise BaseTransaction.DoesNotExist

    # https://bitbucket.org/arcamens/django-payments/wiki/Invoice%20IDs
    @abc.abstractmethod
    def invoice_id(self):
        pass

    def invoiced_item(self):
        return self.item.old_subscription.transaction.item \
            if self.item and self.item.old_subscription \
            else self.item

    @abc.abstractmethod
    def subinvoice(self):
        pass

class SimpleTransaction(BaseTransaction):
    item = models.ForeignKey('SimpleItem', related_name='transactions', null=False, on_delete=models.CASCADE)

    def subinvoice(self):
        return 1

    def invoice_id(self):
        return settings.PAYMENTS_REALM + ' p-%d' % (self.item.pk,)

    def on_accept_regular_payment(self, email):
        payment = SimplePayment.objects.create(transaction=self, email=email)
        self.item.paid = True
        self.item.last_payment = datetime.date.today()
        self.item.upgrade_subscription()
        self.item.save()
        try:
            self.advance_parent(self.item.prolongitem)
        except AttributeError:
            pass
        return payment


    @transaction.atomic
    def advance_parent(self, prolongitem):
        parent_item = SubscriptionItem.objects.select_for_update().get(
            pk=prolongitem.parent_id)  # must be inside transaction
        # parent.email = transaction.email
        base_date = max(datetime.date.today(), parent_item.due_payment_date)
        parent_item.set_payment_date(PayPalUtils.calculate_date(base_date, prolongitem.prolong))
        parent_item.save()


class SubscriptionTransaction(BaseTransaction):
    item = models.ForeignKey('SubscriptionItem', related_name='transactions', null=False, on_delete=models.CASCADE)

    def subinvoice(self):
        return self.invoiced_item().subinvoice

    def invoice_id(self):
        if self.item.old_subscription:
            return settings.PAYMENTS_REALM + ' %d-%d-u' % (self.item.pk, self.subinvoice())
        else:
            return settings.PAYMENTS_REALM + ' %d-%d' % (self.item.pk, self.subinvoice())

    def create_active_subscription(self, ref, email):
        """
        Internal
        """
        # FIXME: UNIQUE constraint for transaction_id fails (https://github.com/vporton/django-debits/issues/10)
        self.item.active_subscription = Subscription.objects.create(transaction=self,
                                                                    subscription_reference=ref,
                                                                    email=email)
        self.item.save()
        return self.item.active_subscription

    @django.db.transaction.atomic
    def obtain_active_subscription(self, ref, email):
        """
        Internal
        """
        if self.item.active_subscription and self.item.active_subscription.subscription_reference == ref:
            return self.item.active_subscription
        else:
            return self.create_active_subscription(ref, email)


class Item(models.Model):
    """
    Apps using this package should create
    their product records manually.

    I may provide an interface for registering
    new products.
    """
    creation_date = models.DateField(auto_now_add=True)

    product = models.ForeignKey('Product', null=True, on_delete=models.CASCADE)
    product_qty = models.IntegerField(default=1)
    blocked = models.BooleanField(default=False)  # hacker or misbehavior detected

    currency = models.CharField(max_length=3, default='USD')
    price = models.DecimalField(max_digits=10, decimal_places=2)  # for recurring payment the amount of one payment
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # code = models.CharField(max_length=255) # TODO
    gratis = models.BooleanField(default=False)  # provide a product or service for free
    # recurring = models.BooleanField(default=False)

    # 0 - no reminder sent
    # 1 - before due payment sent
    # 2 - at due payment sent
    # 3 - day before deadline sent
    reminders_sent = models.SmallIntegerField(default=0, db_index=True)

    # We remove old_subscription automatically when new subscription is created.
    # The new payment may be either one-time (SimpleItem) or subscription (SubscriptionItem).
    old_subscription = models.ForeignKey('Subscription', null=True, related_name='new_subscription', on_delete=models.CASCADE)

    def __repr__(self):
        return "<Item pk=%d, %s>" % (self.pk, self.product.name)

    def __str__(self):
        return self.product.name

    @abc.abstractmethod
    def is_subscription(self):
        pass

    # Can be called from both subscription IPN and payment IPN, so prepare to handle it two times
    @transaction.atomic
    def upgrade_subscription(self):
        if self.old_subscription:
            self.do_upgrade_subscription()

    # TODO: remove ALL old subscriptions as in payment_system2
    def do_upgrade_subscription(self):
        try:
            self.old_subscription.force_cancel(is_upgrade=True)
        except CannotCancelSubscription:
            pass
        # self.on_upgrade_subscription(transaction, item.old_subscription)  # TODO: Needed?
        self.old_subscription = None
        self.save()

    def send_rendered_email(self, template_name, subject, data):
        try:
            self.email = self.subscription.email
        except AttributeError:
            return
        if self.email is None:  # hack!
            return
        self.save()
        html = render_to_string(template_name, data, request=None, using=None)
        text = html2text.HTML2Text(html)
        send_mail(subject, text, settings.FROM_EMAIL, [self.email], html_message=html)

class SimpleItem(Item):
    """
    Non-subscription item.
    """

    paid = models.BooleanField(default=False)

    def is_subscription(self):
        return False

    def is_paid(self):
        return (self.paid or self.gratis) and not self.blocked


class SubscriptionItem(Item):
    item = models.OneToOneField(Item, related_name='subscriptionitem', parent_link=True, on_delete=models.CASCADE)

    active_subscription = models.OneToOneField('Subscription', null=True, on_delete=models.CASCADE)

    due_payment_date = models.DateField(default=datetime.date.today, db_index=True)
    payment_deadline = models.DateField(null=True, db_index=True)  # may include "grace period"
    last_payment = models.DateField(null=True, db_index=True)

    trial = models.BooleanField(default=False, db_index=True)  # now in trial

    grace_period = Period(unit=Period.UNIT_DAYS, count=20)
    payment_period = Period(unit=Period.UNIT_MONTHS, count=1)
    trial_period = Period(unit=Period.UNIT_MONTHS, count=0)

    # https://bitbucket.org/arcamens/django-payments/wiki/Invoice%20IDs
    subinvoice = models.PositiveIntegerField(default=1)  # no need for index, as it is used only at PayPal side

    def is_subscription(self):
        return True

    # Usually you should use quick_is_active() instead because that is faster
    def is_active(self):
        prior = self.payment_deadline is not None and \
                datetime.date.today() <= self.payment_deadline
        return (prior or self.gratis) and not self.blocked

    @staticmethod
    def quick_is_active(item_id):
        item = SubscriptionItem.objects.filter(pk=item_id).\
            only('payment_deadline', 'gratis', 'blocked').get()
        return item.is_active()

    def set_payment_date(self, date):
        self.due_payment_date = date
        self.payment_deadline = PayPalUtils.calculate_date(self.due_payment_date, self.grace_period)

    def start_trial(self):
        if self.trial_period.count != 0:
            self.trial = True
            self.set_payment_date(PayPalUtils.calculate_date(datetime.date.today(), self.trial_period))

    def cancel_subscription(self):
        # atomic operation
        SubscriptionItem.objects.filter(pk=self.pk).update(active_subscription=None,
                                                           subinvoice=F('subinvoice') + 1)
        if not self.old_subscription:  # don't send this email on plan upgrade
            self.cancel_subscription_email()

    def cancel_subscription_email(self):
        url = settings.PAYMENTS_HOST + reverse(settings.PROLONG_PAYMENT_VIEW, args=[self.pk])
        days_before = (self.due_payment_date - datetime.date.today()).days
        self.send_rendered_email('debits/email/subscription-canceled.html',
                                 _("Service subscription canceled"),
                                 {'self': self,
                                  'product': self.product.name,
                                  'url': url,
                                  'days_before': days_before})

    @staticmethod
    def send_reminders():
        SubscriptionItem.send_regular_reminders()
        SubscriptionItem.send_trial_reminders()

    @staticmethod
    def send_regular_reminders():
        # start with the last
        SubscriptionItem.send_regular_before_due_reminders()
        SubscriptionItem.send_regular_due_reminders()
        SubscriptionItem.send_regular_deadline_reminders()

    @staticmethod
    def send_regular_before_due_reminders():
        days_before = settings.PAYMENTS_DAYS_BEFORE_DUE_REMIND
        reminder_date = datetime.date.today() + datetime.timedelta(days=days_before)
        q = SubscriptionItem.objects.filter(reminders_sent__lt=3, due_payment_date__lte=reminder_date, trial=False)
        for transaction in q:
            transaction.reminders_set = 3
            transaction.save()
            url = reverse(settings.PROLONG_PAYMENT_VIEW, args=[transaction.pk])
            transaction.send_rendered_email('debits/email/before-due-remind.html',
                                            _("You need to pay for %s") % transaction.product.name,
                                            {'transaction': transaction,
                                             'product': transaction.product.name,
                                             'url': url,
                                             'days_before': days_before})

    @staticmethod
    def send_regular_due_reminders():
        reminder_date = datetime.date.today()
        q = SubscriptionItem.objects.filter(reminders_sent__lt=2, due_payment_date__lte=reminder_date, trial=False)
        for transaction in q:
            transaction.reminders_set = 2
            transaction.save()
            url = reverse(settings.PROLONG_PAYMENT_VIEW, args=[transaction.pk])
            transaction.send_rendered_email('debits/email/due-remind.html',
                                            _("You need to pay for %s") % transaction.product.name,
                                            {'transaction': transaction,
                                             'product': transaction.product.name,
                                             'url': url})

    @staticmethod
    def send_regular_deadline_reminders():
        reminder_date = datetime.date.today()
        q = SubscriptionItem.objects.filter(reminders_sent__lt=1, payment_deadline__lte=reminder_date, trial=False)
        for transaction in q:
            transaction.reminders_set = 1
            transaction.save()
            url = reverse(settings.PROLONG_PAYMENT_VIEW, args=[transaction.pk])
            transaction.send_rendered_email('debits/email/deadline-remind.html',
                                            _("You need to pay for %s") % transaction.product.name,
                                            {'transaction': transaction,
                                             'product': transaction.product.name,
                                             'url': url})

    @staticmethod
    def send_trial_reminders():
        # start with the last
        SubscriptionItem.send_trial_before_due_reminders()
        SubscriptionItem.send_trial_due_reminders()
        SubscriptionItem.send_trial_deadline_reminders()

    @staticmethod
    def send_trial_before_due_reminders():
        days_before = settings.PAYMENTS_DAYS_BEFORE_TRIAL_END_REMIND
        reminder_date = datetime.date.today() + datetime.timedelta(days=days_before)
        q = SubscriptionItem.objects.filter(reminders_sent__lt=3, due_payment_date__lte=reminder_date, trial=True)
        for transaction in q:
            transaction.reminders_set = 3
            transaction.save()
            url = reverse(settings.PROLONG_PAYMENT_VIEW, args=[transaction.pk])
            transaction.send_rendered_email('debits/email/before-due-remind.html',
                                            _("You need to pay for %s") % transaction.product.name,
                                            {'transaction': transaction,
                                             'product': transaction.product.name,
                                             'url': url,
                                             'days_before': days_before})

    @staticmethod
    def send_trial_due_reminders():
        reminder_date = datetime.date.today()
        q = SubscriptionItem.objects.filter(reminders_sent__lt=2, due_payment_date__lte=reminder_date, trial=True)
        for transaction in q:
            transaction.reminders_set = 2
            transaction.save()
            url = reverse(settings.PROLONG_PAYMENT_VIEW, args=[transaction.pk])
            transaction.send_rendered_email('debits/email/due-remind.html',
                                            _("You need to pay for %s") % transaction.product.name,
                                            {'transaction': transaction,
                                             'product': transaction.product.name,
                                             'url': url})

    @staticmethod
    def send_trial_deadline_reminders():
        reminder_date = datetime.date.today()
        q = SubscriptionItem.objects.filter(reminders_sent__lt=1, payment_deadline__lte=reminder_date, trial=True)
        for transaction in q:
            transaction.reminders_set = 1
            transaction.save()
            url = reverse(settings.PROLONG_PAYMENT_VIEW, args=[transaction.pk])
            transaction.send_rendered_email('debits/email/deadline-remind.html',
                                            _("You need to pay for %s") % transaction.product.name,
                                            {'transaction': transaction,
                                             'product': transaction.product.name,
                                             'url': url})

    # TODO
    # def get_email(self):
    #     try:
    #         # We get the first email, as normally we have no more than one non-canceled transaction
    #         t = self.transactions.filter(subscription__canceled=False)[0]
    #         payment = AutomaticPayment.objects.filter(transaction=t).order_by('-id')[0]
    #         return payment.email
    #     except IndexError:  # no object
    #         return None


class ProlongItem(SimpleItem):
    # item = models.OneToOneField('SimpleItem', related_name='prolongitem', parent_link=True)
    parent = models.ForeignKey('SubscriptionItem', related_name='child', parent_link=False, on_delete=models.CASCADE)
    prolong = Period(unit=Period.UNIT_MONTHS, count=0)  # TODO: rename

    def refund_payment(self):
        prolong2 = self.prolong
        prolong2.count *= -1
        self.parent.set_payment_date(PayPalUtils.calculate_date(self.parent.due_payment_date, prolong2))
        self.parent.save()


class Subscription(models.Model):
    """
    When the user subscribes for automatic payment.
    """

    transaction = models.OneToOneField('SubscriptionTransaction', on_delete=models.CASCADE)

    # Avangate has it for every product, but PayPal for transaction as a whole.
    # So have it both in AutomaticPayment and Subscription
    subscription_reference = models.CharField(max_length=255, null=True)  # as recurring_payment_id in PayPal

    # duplicates email in Payment
    email = models.EmailField(null=True)  # DalPay requires to notify the customer 10 days before every payment

    # TODO: The same as in do_upgrade_subscription()
    #@shared_task  # PayPal tormoz, so run in a separate thread # TODO: celery (with `TypeError: force_cancel() missing 1 required positional argument: 'self'`)
    def force_cancel(self, is_upgrade=False):
        if self.subscription_reference:
            klass = model_from_ref(self.transaction.processor.api)
            api = klass()
            try:
                api.cancel_agreement(self.subscription_reference, is_upgrade=is_upgrade)  # may raise an exception
            except CannotCancelSubscription:
                # fallback
                Subscription.objects.filter(pk=self.pk).update(subscription_reference=None)
                logger.warn("Cannot cancel subscription " + self.subscription_reference)
            # transaction.cancel_subscription()  # runs in the callback


class Payment(models.Model):
    email = models.EmailField(null=True)  # DalPay requires to notify the customer 10 days before every payment

    def refund_payment(self):
        try:
            self.transaction.item.prolongitem.refund_payment()
        except ObjectDoesNotExist:
            pass


class SimplePayment(Payment):
    transaction = models.OneToOneField('SimpleTransaction', on_delete=models.CASCADE)


class AutomaticPayment(Payment):
    """
    This class models automatic payment.
    """

    # The transaction which corresponds to the starting
    # process of purchase.
    transaction = models.ForeignKey('SubscriptionTransaction', on_delete=models.CASCADE)

    # subscription = models.ForeignKey('Subscription')

    # curr = models.CharField(max_length=3, default='USD')

    # A transaction should have a code that identifies it.
    # code = models.CharField(max_length=255)


class CannotCancelSubscription(Exception):
    pass

class CannotRefundSubscription(Exception):
    pass
