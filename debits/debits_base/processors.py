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


def hidden_field(f, v):
    """Internal."""
    return "<input type='hidden' name='%s' value='%s'/>" % (escape(f), escape(v))


class BasePaymentProcessor(abc.ABC):
    """Executing a transaction for a particular payment processor (by a derived class).

    We receive a derivative of :class:`~debits.debits_base.models.BaseTransaction` object
    and a hash (see for example PayPay documentation) from user.

    Then the hash is amended (for example added the price from the transaction object) and
    passed to the payment processor.
    """
    @abc.abstractmethod
    def amend_hash_new_purchase(self, transaction, hash):
        """Internal."""
        pass

    def amend_hash_change_subscription(self, transaction, hash):
        """Internal."""
        raise NotImplementedError()

    def change_subscription(self, transaction, hash):
        """Start the process of changing a subscription with given hash and transaction."""
        hash = self.amend_hash_change_subscription(transaction, hash)
        return self.redirect_to_processor(hash)

    def make_purchase(self, hash, transaction):
        """Start the process of purchase with given hash and transaction."""
        hash = self.amend_hash_new_purchase(transaction, hash)
        return self.redirect_to_processor(hash)

    def make_purchase_from_form(self, hash, transaction):
        """Start the process of purchase with hash received from a HTML form and transaction."""
        hash = dict(hash)
        del hash['csrfmiddlewaretoken']
        # immediately before redirect to the processor
        return self.make_purchase(hash, transaction)

    def change_subscription_from_form(self, hash):
        """Start the process of changing a subscription with hash received from a HTML form and transaction."""
        hash = dict(hash)
        transaction = debits.debits_base.models.Item.objects.get(hash['arcamens_purchaseid'])
        del hash['arcamens_purchaseid']
        hash = self.amend_hash_change_subscription(transaction, hash)
        return self.change_subscription(transaction, hash)

    def redirect_to_processor(self, hash):
        """Internal."""
        return HttpResponse(BasePaymentProcessor.html(hash))

    # Internal
    # Use this instead of a redirect because we prefer POST over GET
    @staticmethod
    def html(hash):
        """Internal."""
        action = escape(hash['arcamens_action'])
        del hash['arcamens_action']
        return "<html><head><meta charset='utf-8'' /></head>\n" +\
            "<body onload='document.forms[0].submit()'>\n<p>Redirecting...</p>\n" + \
            "<form method='post' action='"+action+"'>\n" + \
            '\n'.join([hidden_field(i[0], str(i[1])) for i in hash.items()]) + \
            "\n</form></body></html>"

    def ready_for_subscription(self, transaction):
        """Check if ready for subscription.

        If we are in manual recurring mode, we can be not ready for subscription,
        because some payment processors (PayPal) don't allow to delay the first
        payment of a subscription for more than :meth:`self.subscription_allowed_date` days."""
        return datetime.date.today() >= self.subscription_allowed_date(transaction)

    @abc.abstractmethod
    def subscription_allowed_date(self, transaction):
        """See :meth:`ready_for_subscription`."""
        pass

    def product_name(self, item):
        """Internal."""
        return item.product.name


PAYMENT_PROCESSOR_AVANGATE = 1
PAYMENT_PROCESSOR_PAYPAL = 2
PAYMENT_PROCESSOR_BRAINTREE = 3
PAYMENT_PROCESSOR_DALPAY = 4
PAYMENT_PROCESSOR_RECURLY = 5


class PaymentCallback(object):
    """Mixin this class to make callbacks on a payment.

    In current implementation, :meth:`on_subscription_created` may be called when it was already started
    and :meth:`on_subscription_canceled` may be called when it is already stopped.
    (In other words, they can be called multiple times in a row.)
    """
    def on_payment(self, payment):
        """Called on any payment (subscription or regular)."""
        pass

    # def on_upgrade_subscription(self, transaction, old_subscription):
    #     pass

    def on_subscription_created(self, POST, subscription):
        """Called when a subscription is created."""
        pass

    def on_subscription_canceled(self, POST, subscription):
        """Called when a subscription is canceled."""
        pass
