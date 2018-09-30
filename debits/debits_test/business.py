from django.db import transaction

import debits
from debits.debits_base.base import Period
from .models import Organization, MyPurchase, PricingPlan


# TODO: Move .plan to Plan?
@transaction.atomic
def create_organization(name, pricing_plan_id, trial_months):
    """Creates a new example organization.

    It also associates a :class:`~debits.debits_test.models.MyPurchase` with it."""
    plan = PricingPlan.objects.get(pk=pricing_plan_id)
    item = debits.debits_base.models.SubscriptionItem.objects.create(product=plan.product,
                                                                     currency=plan.currency,
                                                                     price=plan.price,
                                                                     payment_period_unit=Period.UNIT_MONTHS,
                                                                     payment_period_count=1,
                                                                     trial_period_unit=Period.UNIT_MONTHS,
                                                                     trial_period_count=trial_months)
    purchase = MyPurchase(item=item, plan=plan)
    if trial_months:
        purchase.start_trial()
    purchase.save()
    org = Organization.objects.create(name=name, purchase=purchase)
    purchase.for_organization = org
    purchase.save()
    return org
