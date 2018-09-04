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
        organization = item.for_purchase.for_organization  # FIXME: item has no purchase
        if organization is None:
            return
        organization.purchase = item.for_purchase
        organization.save()
