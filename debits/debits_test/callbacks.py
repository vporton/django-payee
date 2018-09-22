from debits.debits_base.models import AutomaticPayment
from debits.paypal.views import PayPalIPN


class MyPayPalIPN(PayPalIPN):
    """Mixin to handle purchase events.

    Two subscription IPNs may call both :meth:`on_subscription_created` and :meth:`on_payment`.
    It is not a problem (if not to count a tiny performance lag).

    TODO: Generalize it for non PayPal processors."""
    def on_subscription_created(self, POST, subscription):
        item = subscription.transaction.payment.item
        self.do_purchase(item)

    def on_payment(self, payment):
        if isinstance(payment, AutomaticPayment):
            item = payment.transaction.item
            self.do_purchase(item)

    def do_purchase(self, item):
        """Set the :class:`~debits.debits_test.models.Purchase` for an :class:`~debits.debits_test.models.Organization`."""
        organization = item.subscriptionitem.purchase.for_organization
        if organization is not None:
            organization.purchase = item.subscriptionitem.purchase
            organization.save()
