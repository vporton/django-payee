import datetime

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, reverse
from django.utils.translation import ugettext_lazy as _
from .models import Organization, MyPurchase, PricingPlan
from .forms import CreateOrganizationForm, SwitchPricingPlanForm
from .business import create_organization
from debits.debits_base.base import Period, period_to_string
from debits.debits_base.models import SimpleTransaction, SubscriptionTransaction, ProlongPurchase, SubscriptionItem, \
    logger, \
    CannotCancelSubscription, ProlongPurchase, SimpleItem
import debits
from .processors import MyPayPalForm


def transaction_payment_view(request, transaction_id):
    """A view initiated from a transaction."""
    transaction = SubscriptionTransaction.objects.get(pk=int(transaction_id))
    purchase = transaction.purchase
    organization = purchase.organization
    return do_organization_payment_view(request, purchase, organization)


def organization_payment_view(request, organization_id):
    """A view initiated for an organization."""
    organization = Organization.objects.get(pk=int(organization_id))
    purchase = organization.purchase
    return do_organization_payment_view(request, purchase, organization)


def do_organization_payment_view(request, purchase, organization):
    """The common pars of views for :func:`transaction_payment_view` and :func:`organization_payment_view`."""
    plan_form = SwitchPricingPlanForm({'pricing_plan': purchase.plan.pk})
    pp = MyPayPalForm(request)
    return render(request, 'debits_test/organization-payment-view.html',
                  {'organization_id': organization.pk,
                   'organization': organization.name,
                   'item_id': purchase.pk,
                   'email': purchase.payment.email if purchase.payment else None,
                   'gratis': purchase.gratis,
                   'active': purchase.is_active(),
                   'blocked': purchase.blocked,
                   'manual_mode': not purchase.subscribed,
                   'processor_name': purchase.processor.name if purchase.processor else None,
                   # only for automatic recurring payment
                   'plan': purchase.plan.name,
                   'trial': purchase.trial,
                   'trial_period': period_to_string(purchase.item.subscriptionitem.trial_period),
                   'due_date': purchase.due_payment_date,
                   'deadline': purchase.payment_deadline,
                   'price': purchase.item.price,
                   'currency': purchase.item.currency,
                   'payment_period': period_to_string(purchase.item.subscriptionitem.payment_period),
                   'plan_form': plan_form,
                   'can_switch_to_recurring': pp.ready_for_subscription(purchase),
                   'subscription_allowed_date': pp.subscription_allowed_date(purchase),
                   'subscription_reference': purchase.subscription_reference,
                   'subinvoice': purchase.subinvoice})


def create_organization_view(request):
    """The view to create an example organization."""
    if request.method == 'POST':
        form = CreateOrganizationForm(request.POST)
        if form.is_valid():
            trial_months = 1 if 'use_trial' in request.POST else 0
            organization = create_organization(request.POST['name'], int(request.POST['pricing_plan']), trial_months)
            return HttpResponseRedirect(reverse('organization-prolong-payment', args=[organization.pk]))
    else:
        form = CreateOrganizationForm()

    return render(request, 'debits_test/create-organization.html', {'form': form})


def get_processor(request, hash):
    """Determine the payment processor, from a form."""
    processor_name = hash.pop('arcamens_processor')
    if processor_name == 'PayPal':
        form = MyPayPalForm(request)
        processor_id = debits.debits_base.processors.PAYMENT_PROCESSOR_PAYPAL
        processor = debits.debits_base.models.PaymentProcessor.objects.get(pk=processor_id)
    else:
        raise RuntimeError("Unsupported payment form.")
    return form, processor


def do_subscribe(hash, form, processor, purchase):
    """Start subscription to our subscription purchase."""
    transaction = SubscriptionTransaction.objects.create(processor=processor, purchase=purchase)
    return form.make_purchase_from_form(hash, transaction)


def do_prolong(hash, form, processor, purchase):
    """Start prolonging our subscription purchase."""
    periods = int(hash['periods'])
    subitem = SimpleItem.objects.create(product=purchase.item.product,
                                        currency=purchase.item.currency,
                                        price=purchase.item.price * periods)
    subpurchase = ProlongPurchase.objects.create(item=subitem,
                                                 prolonged=purchase,
                                                 period_unit=Period.UNIT_MONTHS,
                                                 period_count=periods)
    subtransaction = SimpleTransaction.objects.create(processor=processor, purchase=subpurchase)
    return form.make_purchase_from_form(hash, subtransaction)


def upgrade_calculate_new_period(k, purchase):
    """New period (in days) after an upgrade."""
    if purchase.due_payment_date:
        period = (purchase.due_payment_date - datetime.date.today()).days
    else:
        period = 0
    return round(period / k) if k > 1 else period  # don't increase paid period when downgrading


def upgrade_create_new_item(old_purchase, plan, new_period, organization):
    """Create new purchase used to upgrade another purchase (:obj:`old_purchase`)."""
    item = debits.debits_base.models.SubscriptionItem.objects.create(
        product=plan.product,
        currency=plan.currency,
        price=plan.price,
        payment_period_unit=Period.UNIT_MONTHS,
        payment_period_count=1,
        trial_period_unit=Period.UNIT_DAYS,
        trial_period_count=new_period)
    purchase = MyPurchase(item=item,
                          for_organization=organization,
                          plan=plan)
    purchase.set_payment_date(datetime.date.today() + datetime.timedelta(days=new_period))
    if old_purchase.subscribed:
        purchase.old_subscription = old_purchase
    purchase.save()
    return purchase


def do_upgrade(hash, form, processor, purchase, organization):
    """Start upgrading a subscription purchase,"""
    plan = PricingPlan.objects.get(pk=int(hash.pop('pricing_plan')))
    if plan.currency != purchase.item.currency:
        raise RuntimeError(_("Cannot upgrade to a payment plan with other currency."))
    if purchase.item.subscriptionitem.payment_period.unit != Period.UNIT_MONTHS or purchase.item.subscriptionitem.payment_period.count != 1:
        raise RuntimeError(_("Only one month payment period supported."))

    k = plan.price / purchase.item.price  # price multiplies
    new_period = upgrade_calculate_new_period(k, purchase)

    new_purchase = upgrade_create_new_item(purchase, plan, new_period, organization)

    if not purchase.subscribed:
        # Simply create a new purchase which can be paid later
        organization.purchase = new_purchase
        organization.save()
        return HttpResponseRedirect(reverse('organization-prolong-payment', args=[organization.pk]))
    else:
        upgrade_transaction = SubscriptionTransaction.objects.create(processor=processor, purchase=new_purchase)
        return form.make_purchase_from_form(hash, upgrade_transaction)


def purchase_view(request):
    """The main test view to make purchases, subscriptions, upgrades."""
    hash = request.POST.dict()
    op = hash.pop('arcamens_op')
    form, processor = get_processor(request, hash)
    organization_pk = int(hash.pop('organization'))  # in real code should use user login information
    organization = Organization.objects.get(pk=organization_pk)
    purchase = organization.purchase
    if op == 'subscribe':
        due_date = purchase.due_payment_date
        if due_date < datetime.date.today():
            due_date = datetime.date.today()
        new_item = debits.debits_base.models.SubscriptionItem.objects.create(
            product=purchase.plan.product,
            currency=purchase.plan.currency,
            price=purchase.plan.price,
            payment_period_unit=Period.UNIT_MONTHS,
            payment_period_count=1,
            trial_period_unit=Period.UNIT_DAYS,
            trial_period_count=(due_date - datetime.date.today()).days)
        new_purchase = MyPurchase(item=new_item,
                                  for_organization=organization,
                                  plan=purchase.plan)
        new_purchase.set_payment_date(due_date)
        new_purchase.save()
        return do_subscribe(hash, form, processor, new_purchase)
    elif op == 'manual':
        return do_prolong(hash, form, processor, purchase)
    elif op == 'upgrade':
        return do_upgrade(hash, form, processor, purchase, organization)


# TODO: purchase argument is not used
def do_unsubscribe(purchase):
    try:
        purchase.force_cancel()
    except CannotCancelSubscription as e:
        return HttpResponse(e)
    else:
        return HttpResponse('')  # empty string means success


def unsubscribe_organization_view(request, organization_pk):
    """Django view for the "Unsubscribe" button."""
    organization_pk = int(organization_pk)  # in real code should use user login information
    organization = Organization.objects.get(pk=organization_pk)
    purchase = organization.purchase.subscriptionpurchase
    return do_unsubscribe(purchase)
    # return HttpResponseRedirect(reverse('organization-prolong-payment', args=[organization.pk]))


def list_organizations_view(request):
    """Django view to list all the organizations."""
    list = [{'id': o.id, 'name': o.name} for o in Organization.objects.all()]
    return render(request, 'debits_test/list-organizations.html',
                  {'organizations': list})
