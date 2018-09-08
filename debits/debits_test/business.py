from django.db import transaction
from debits.debits_base.base import Period
from .models import Organization, Purchase, PricingPlan


@transaction.atomic
def create_organization(name, pricing_plan_id, trial_months):
    """Creates a new example organization.

    It also associates a :class:`~debits.debits_test.models.Purchase` with it."""
    plan = PricingPlan.objects.get(pk=pricing_plan_id)
    purchase = Purchase(plan=plan,
                        product=plan.product,
                        currency=plan.currency,
                        price=plan.price,
                        payment_period_unit=Period.UNIT_MONTHS,
                        payment_period_count=1,
                        trial_period_unit=Period.UNIT_MONTHS,
                        trial_period_count=trial_months)
    if trial_months:
        purchase.start_trial()
    purchase.save()
    org = Organization.objects.create(name=name, purchase=purchase)
    purchase.for_organization = org
    purchase.save()
    return org