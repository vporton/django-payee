from payee.payee_base.processors import BasePaymentProcessor

class AvangateForm(BasePaymentProcessor):
    def amend_hash_new_purchase(self, transaction, hash):
        items = {}

        # FIXME
