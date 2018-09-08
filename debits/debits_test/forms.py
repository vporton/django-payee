from django import forms
from django.utils.translation import ugettext_lazy as _
from .models import PricingPlan
from .products import PRODUCT_ITEM_1

class CreateOrganizationForm(forms.Form):
    """Django form to create a new example organization."""
    name = forms.CharField(label=_('Organization name'))
    pricing_plan = forms.ModelChoiceField(PricingPlan.objects.filter(product=PRODUCT_ITEM_1),
                                          label=_('Pricing plan'))
    use_trial = forms.BooleanField(label=_('With trial period'), required=False)


class SwitchPricingPlanForm(forms.Form):
    """Django form to switch pricing plan."""
    pricing_plan = forms.ModelChoiceField(PricingPlan.objects.filter(product=PRODUCT_ITEM_1))
