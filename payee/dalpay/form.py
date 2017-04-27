from django.utils.translation import ugettext_lazy as _
from payee.payee_base.processors import BasePaymentProcessor
from django.conf import settings


# See DalPay Checkout Integration Guide about:
# - page_id
# - pay_type
# - cust_name, cust_company, etc.
class DalPalForm(BasePaymentProcessor):
    def amend_hash_new_purchase(self, transaction, hash):
        items = {}

        # Non-recurring items:
        i = 1
        for purchase in transaction.purchase_set.all():
            if not purchase.recurring:
                items['item%s_desc' % (i+1)] = purchase.product.name
                items['item%s_price' % (i+1)] = purchase.price
                items['item%s_qty' % (i+1)] = purchase.product_qty
                i += 1
        hash.update({
            'mer_id': settings.DALPAY_MERCHANT_ID,
            'num_items': transaction.purchase_set.count(),
        })
        hash.update(items)

        # Recurring items:
        recurring_amount = 0
        for purchase in transaction.purchase_set.all():
            if purchase.recurring:
                recurring_amount += purchase.price
        if recurring_amount != 0:
            hash['rebill_type'] = 'monthly-' + str(recurring_amount)
            hash['rebill_desc'] = _("Arcamens company Web services")  # FIXME

    # FIXME
    def amend_hash_change_subscription(self, transaction, hash):
        pass
