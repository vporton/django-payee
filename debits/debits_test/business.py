from django.db import transaction

import debits
from debits.debits_base.base import Period
from .models import Organization, MyPurchase, PricingPlan


@transaction.atomic
def create_organization(name, pricing_plan_id, trial_months):
    """Creates a new example organization.

    It also associates a :class:`~debits.debits_test.models.MyPurchase` with it."""
    plan = PricingPlan.objects.get(pk=pricing_plan_id)
    item = plan
    item.reset()
    item.save()
    purchase = MyPurchase(item=item)
    if trial_months:
        purchase.start_trial()
    purchase.save()
    org = Organization.objects.create(name=name, purchase=purchase)
    purchase.for_organization = org
    purchase.save()
    return org
