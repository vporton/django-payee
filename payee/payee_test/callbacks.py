from payee.paypal.views import PayPalIPN


class MyPayPalIPN(PayPalIPN):
    # Two subscription IPNs may call both below methods. It is not a problem (if not to count a tiny performance lag).
    def on_subscription_created(self, POST, subscription):
        subscriptionitem = subscription.subscriptiontransaction.item
        organization = subscriptionitem.purchase.for_organization
        if organization is None:
            return
        organization.purchase = subscriptionitem.purchase
        organization.save()

    # FIXME: Make it called only in subscription payments
    def on_payment(self, payment):
        subscriptionitem = payment.subscriptiontransaction.item
        organization = subscriptionitem.purchase.for_organization
        if organization is None:
            return
        organization.purchase = subscriptionitem.purchase
        organization.save()
