from decimal import Decimal
import datetime
from django.db.models import F
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, reverse
from django.utils.translation import ugettext_lazy as _
from .models import Organization, Purchase, PricingPlan
from .forms import CreateOrganizationForm, SwitchPricingPlanForm
from .business import create_organization
from payee.payee_base.models import SimpleTransaction, SubscriptionTransaction, Period, ProlongItem, SubscriptionItem, period_to_string, logger, CannotCancelSubscription
import payee
from .processors import MyPayPalForm

def transaction_payment_view(request, transaction_id):
    transaction = SubscriptionTransaction.objects.get(pk=int(transaction_id))
    purchase = transaction.purchase
    organization = purchase.organization
    return do_organization_payment_view(request, transaction, organization, purchase)


def organization_payment_view(request, organization_id):
    organization = Organization.objects.get(pk=int(organization_id))
    purchase = organization.purchase
    item = purchase.item
    return do_organization_payment_view(request, item, organization, purchase)


def do_organization_payment_view(request, item, organization, purchase):
    plan_form = SwitchPricingPlanForm({'pricing_plan': purchase.plan.pk})
    pp = MyPayPalForm(request)
    return render(request, 'payee_test/organization-payment-view.html',
                  {'organization_id': organization.pk,
                   'organization': organization.name,
                   'item_id': item.pk,
                   'email': item.active_subscription.email if item.active_subscription else None,
                   'gratis': item.gratis,
                   'active': item.is_active(),
                   'blocked': item.blocked,
                   'manual_mode': not item.active_subscription,
                   'processor_name': item.active_subscription.transaction.processor.name if item.active_subscription else None,  # only for automatic recurring payee
                   'plan': purchase.plan.name,
                   'trial': item.trial,
                   'trial_period': period_to_string(item.trial_period),
                   'due_date': item.due_payment_date,
                   'deadline': item.payment_deadline,
                   'price': item.price,
                   'currency': item.currency,
                   'payment_period': period_to_string(item.payment_period),
                   'plan_form': plan_form,
                   'can_switch_to_recurring': pp.ready_for_subscription(item),
                   'subscription_allowed_date': pp.subscription_allowed_date(item),
                   'subscription_reference': item.active_subscription.subscription_reference if item.active_subscription else None,
                   'subinvoice': item.subinvoice})


def create_organization_view(request):
    if request.method == 'POST':
        form = CreateOrganizationForm(request.POST)
        if form.is_valid():
            trial_months = 1 if 'use_trial' in request.POST else 0
            organization = create_organization(request.POST['name'], int(request.POST['pricing_plan']), trial_months)
            return HttpResponseRedirect(reverse('organization-prolong-payment', args=[organization.pk]))
    else:
        form = CreateOrganizationForm()

    return render(request, 'payee_test/create-organization.html', {'form': form})


def get_processor(request, hash):
    processor_name = hash.pop('arcamens_processor')
    if processor_name == 'PayPal':
        form = MyPayPalForm(request)
        processor_id = payee.payee_base.processors.PAYMENT_PROCESSOR_PAYPAL
        processor = payee.payee_base.models.PaymentProcessor.objects.get(pk=processor_id)
    else:
        raise RuntimeError("Unsupported payment form.")
    return form, processor


def do_subscribe(hash, form, processor, item):
    transaction = SubscriptionTransaction.objects.create(processor=processor, item=item)
    return form.make_purchase_from_form(hash, transaction)


def do_prolong(hash, form, processor, item):
    periods = int(hash['periods'])
    subitem = ProlongItem.objects.create(product=item.product,
                                         currency=item.currency,
                                         price=item.price * periods,
                                         parent=item,
                                         prolong_unit=Period.UNIT_MONTHS,
                                         prolong_count=periods)
    subtransaction = SimpleTransaction.objects.create(processor=processor, item=subitem.item)
    return form.make_purchase_from_form(hash, subtransaction)


def upgrade_calculate_new_period(k, item):
    if item.due_payment_date:
        period = (item.due_payment_date - datetime.date.today()).days
    else:
        period = 0
    return round(period / k) if k > 1 else period  # don't increase paid period when downgrading


def upgrade_create_new_item(item, plan, new_period):
    new_item = SubscriptionItem(product=item.product,
                                currency=plan.currency,
                                price=plan.price,
                                trial=item.trial,
                                payment_period_unit=Period.UNIT_MONTHS,
                                payment_period_count=1,
                                trial_period_unit=item.trial_period_unit,
                                trial_period_count=item.trial_period_count)
    new_item.set_payment_date(datetime.date.today() + datetime.timedelta(days=new_period))
    if item.active_subscription:
        new_item.old_subscription = item.active_subscription
    new_item.adjust_dates()
    new_item.save()
    return new_item


def upgrade_subscription(organization, item, new_item, plan):
    try:
        item.active_subscription.force_cancel()
    except CannotCancelSubscription:
        pass
    item.active_subscription = None
    item.save()
    organization.purchase = Purchase.objects.create(plan=plan, item=new_item)
    organization.save()
    return HttpResponseRedirect(reverse('organization-prolong-payment', args=[organization.pk]))


def do_upgrade(hash, form, processor, item, organization):
    plan = PricingPlan.objects.get(pk=int(hash['pricing_plan']))
    if plan.currency != item.currency:
        raise RuntimeError(_("Cannot upgrade to a payment plan with other currency."))
    if item.payment_period.unit != Period.UNIT_MONTHS or item.payment_period.count != 1:
        raise RuntimeError(_("Only one month payment period supported."))

    k = plan.price / item.price  # price multiplies
    new_period = upgrade_calculate_new_period(k, item)

    new_item = upgrade_create_new_item(item, plan, new_period)

    if not item.active_subscription:
        # Simply create a new purchase which can be paid later
        organization.purchase = Purchase.objects.create(plan=plan, item=new_item)
        organization.save()
        return HttpResponseRedirect(reverse('organization-prolong-payment', args=[organization.pk]))
    elif k <= 1:
        return upgrade_subscription(organization, item, new_item, plan)
    else:
        upgrade_transaction = SubscriptionTransaction.objects.create(processor=processor, item=new_item)
        Purchase.objects.create(plan=plan, item=new_item, for_organization=organization)
        return form.make_purchase_from_form(hash, upgrade_transaction)


def purchase_view(request):
    hash = request.POST.dict()
    op = hash.pop('arcamens_op')
    form, processor = get_processor(request, hash)
    organization_pk = int(hash.pop('organization'))  # in real code should use user login information
    organization = Organization.objects.get(pk=organization_pk)
    purchase = organization.purchase
    item = purchase.item
    if op == 'subscribe':
        return do_subscribe(hash, form, processor, item)
    elif op == 'manual':
        return do_prolong(hash, form, processor, item)
    elif op == 'upgrade':
        return do_upgrade(hash, form, processor, item, organization)


def do_unsubscribe(subscription, item):
    try:
        if not subscription:
            raise CannotCancelSubscription(_("Subscription was already canceled"))
        subscription.force_cancel()
    except CannotCancelSubscription as e:
        # Without active_subscription=None it may remain in falsely subscribed state without a way to exit
        SubscriptionItem.objects.filter(pk=item.pk).update(active_subscription=None,
                                                           subinvoice=F('subinvoice') + 1)
        return HttpResponse(e)
    else:
        return HttpResponse('')  # empty string means success


def unsubscribe_organization_view(request, organization_pk):
    organization_pk = int(organization_pk)  # in real code should use user login information
    organization = Organization.objects.get(pk=organization_pk)
    item = organization.purchase.item
    subscription = item.active_subscription
    do_unsubscribe(subscription, item)
    # return HttpResponseRedirect(reverse('organization-prolong-payment', args=[organization.pk]))


def list_organizations_view(request):
    list = [{'id': o.id, 'name': o.name} for o in Organization.objects.all()]
    return render(request, 'payee_test/list-organizations.html',
                  {'organizations': list})
