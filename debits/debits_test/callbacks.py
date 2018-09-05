from debits.debits_base.models import AutomaticPayment
from debits.paypal.views import PayPalIPN


class MyPayPalIPN(PayPalIPN):
    # Two subscription IPNs may call both below methods. It is not a problem (if not to count a tiny performance lag).
    def on_subscription_created(self, POST, subscription):
        item = subscription.transaction.item
        self.do_purchase(item)

    def on_payment(self, payment):
        if isinstance(payment, AutomaticPayment):
            item = payment.transaction.item
            self.do_purchase(item)

    def do_purchase(self, item):
        organization = item.purchase.for_organization
        if organization is not None:
            organization.purchase = item.purchase
            organization.save()
