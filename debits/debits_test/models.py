from django.db import models
from debits.debits_base.base import Period
from debits.debits_base.models import Product, SubscriptionPurchase, SubscriptionItem


class PricingPlan(SubscriptionItem):
    """Pricing plan (like "Item 1", $10/month)."""

    plan_name = models.CharField(max_length=255)
    """Pricing plan name."""

    def __str__(self):
        return self.product.name + ': ' + self.plan_name

    def __repr__(self):
        return "<PricingPlan: %s, %s>" % ((("pk=%d" % self.pk) if self.pk else "no pk"), self.__str__())


class MyPurchase(SubscriptionPurchase):
    """An example purchase."""

    for_organization = models.ForeignKey('Organization', null=True, related_name='for_purchase', on_delete=models.CASCADE)
    """The organization for which the purchase was initiated.
    
    Don't mess :attr:`for_organization` with :attr:`organization`!"""

    def __repr__(self):
        return "<MyPurchase: %s>" % (("pk=%d" % self.pk) if self.pk else "no pk")


class Organization(models.Model):
    """An example organization."""

    name = models.CharField(max_length=255)
    """Organization name."""

    purchase = models.OneToOneField(MyPurchase, on_delete=models.CASCADE)
    """The current active :class:`~debits.debits_test.models.MyPurchase` for the organization."""

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Organization: %s, %s>" % ((("pk=%d" % self.pk) if self.pk else "no pk"), self.__str__())
