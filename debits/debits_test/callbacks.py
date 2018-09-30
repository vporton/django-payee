from debits.debits_base.models import AutomaticPayment
from debits.paypal.views import PayPalIPN


class MyPayPalIPN(PayPalIPN):
    """Mixin to handle purchase events.

    Two subscription IPNs may call both :meth:`on_subscription_created` and :meth:`on_payment`.
    It is not a problem (if not to count a tiny performance lag).

    TODO: Generalize it for non PayPal processors."""
    def on_subscription_created(self, POST, purchase):
        self.do_purchase(purchase)

    def on_payment(self, payment):
        if isinstance(payment, AutomaticPayment):
            purchase = payment.transaction.purchase
            self.do_purchase(purchase)

    def do_purchase(self, purchase):
        """Set the :class:`~debits.debits_test.models.MyPurchase` for an :class:`~debits.debits_test.models.Organization`."""
        organization = purchase.subscriptionpurchase.mypurchase.for_organization
        if organization is not None:
            organization.purchase = purchase.subscriptionpurchase.mypurchase
            organization.save()
