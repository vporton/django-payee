import debits.debits_base
from debits.debits_base.models import SubscriptionItem
import abc
import datetime
from django.http import HttpResponse
try:
    from html import escape  # python 3.x
except ImportError:
    from cgi import escape  # python 2.x
import debits.debits_base


# Internal
def hidden_field(f, v):
    return "<input type='hidden' name='%s' value='%s'/>" % (escape(f), escape(v))


# We receive a hash from user (see for example DalPay documentation).
# The hash is stored in the DB.
# Then the hash is amended (for example added the price) and passed to the payment processor.
class BasePaymentProcessor(abc.ABC):
    @abc.abstractmethod
    def amend_hash_new_purchase(self, transaction, hash):
        pass

    def amend_hash_change_subscription(self, transaction, hash):
        raise NotImplementedError()

    def real_make_purchase(self, hash, transaction):
        hash = self.amend_hash_new_purchase(transaction, hash)
        return self.redirect_to_processor(hash)

    def change_subscription(self, transaction, hash):
        hash = self.amend_hash_change_subscription(transaction, hash)
        return self.redirect_to_processor(hash)

    # TODO: These two methods do the same
    def make_purchase(self, hash, transaction):
        return self.real_make_purchase(hash, transaction)

    def make_purchase_from_form(self, hash, transaction):
        hash = dict(hash)
        del hash['csrfmiddlewaretoken']
        # immediately before redirect to the processor
        return self.make_purchase(hash, transaction)

    def change_subscription_from_form(self, hash):
        hash = dict(hash)
        transaction = debits.debits_base.models.Item.objects.get(hash['arcamens_purchaseid'])
        del hash['arcamens_purchaseid']
        hash = self.amend_hash_change_subscription(transaction, hash)
        return self.change_subscription(transaction, hash)

    def redirect_to_processor(self, hash):
        return HttpResponse(BasePaymentProcessor.html(hash))

    # Internal
    # Use this instead of a redirect because we prefer POST over GET
    @staticmethod
    def html(hash):
        action = escape(hash['arcamens_action'])
        del hash['arcamens_action']
        return "<html><head><meta charset='utf-8'' /></head>\n" +\
            "<body onload='document.forms[0].submit()'>\n<p>Redirecting...</p>\n" + \
            "<form method='post' action='"+action+"'>\n" + \
            '\n'.join([hidden_field(i[0], str(i[1])) for i in hash.items()]) + \
            "\n</form></body></html>"

    # Makes sense only in manual recurring mode
    def ready_for_subscription(self, transaction):
        return datetime.date.today() >= self.subscription_allowed_date(transaction)

    @abc.abstractmethod
    def subscription_allowed_date(self, transaction):
        pass

    def product_name(self, item):
        return item.product.name


PAYMENT_PROCESSOR_AVANGATE = 1
PAYMENT_PROCESSOR_PAYPAL = 2
PAYMENT_PROCESSOR_BRAINTREE = 3
PAYMENT_PROCESSOR_DALPAY = 4
PAYMENT_PROCESSOR_RECURLY = 5


# In current implementation, on_subscription_start() may be called when it was already started
# and on_subscription_stop() may be called when it is already stopped
class PaymentCallback(object):
    def on_payment(self, payment):
        pass

    def on_subscription_start(self, subscription):
        pass

    def on_subscription_stop(self, subscription):
        pass

    # def on_upgrade_subscription(self, transaction, old_subscription):
    #     pass

    def on_subscription_created(self, POST, subscription):
        pass

    def on_subscription_canceled(self, POST, subscription):
        pass
