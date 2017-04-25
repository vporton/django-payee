from django.db import transaction
from payments.payments_base.models import SubscriptionItem, Period
from .models import Organization, Purchase, PricingPlan


@transaction.atomic
def create_organization(name, pricing_plan_id, trial_months):
    plan = PricingPlan.objects.get(pk=pricing_plan_id)
    item = SubscriptionItem(product=plan.product,
                            currency=plan.currency,
                            price=plan.price,
                            payment_period_unit=Period.UNIT_MONTHS,
                            payment_period_count=1,
                            trial_period_unit=Period.UNIT_MONTHS,
                            trial_period_count=trial_months)
    if trial_months:
        item.start_trial()
    item.save()
    purchase = Purchase.objects.create(plan=plan, item=item)
    return Organization.objects.create(name=name, purchase=purchase)