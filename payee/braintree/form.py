from django.db import transaction
from django.apps import apps
import braintree

# FIXME

class BrainTreeForm:
    def render(self, product, price, recurring, old_recurring):
        pass

    # def create_payment_method(self, request):
    #     with transaction.atomic():  # FIXME
    #         user = apps.get_model('User').objects.get(id=request.session['user_id'])
    #         customer = user.braintreecustomer
    #         if not customer:

    def start_transaction(self, product, price, recurring, old_recurring, plan):
        client_token = braintree.ClientToken.generate({'options': 'make_default'})
        result = braintree.Transaction.sale({
            "amount": price,
            'recurring': recurring,
            'purchase_order_number': product,
            'payment_method_token': client_token,
            "options": {
                'submit_for_settlement': True,
                'store_in_vault_on_success': True  # required for recurring payee
            }
        })
        # https://developers.braintreepayments.com/guides/recurring-billing/overview
    # FIXME: PaymentMethod.update()