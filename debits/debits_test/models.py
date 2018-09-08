from django.db import models
from debits.debits_base.base import Period
from debits.debits_base.models import Product, SubscriptionItem


class PricingPlan(models.Model):
    """Pricing plan (like "Item 1", $10/month)."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    """Sold product."""

    name = models.CharField(max_length=255)
    """Pricing plan name."""

    price = models.DecimalField(max_digits=10, decimal_places=2)
    """The price of each recurring payment."""

    currency = models.CharField(max_length=3)
    """The currency of payments."""

    period = Period()
    """Recurring payments period."""

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<PricingPlan: %s, %s>" % ((("pk=%d" % self.pk) if self.pk else "no pk"), self.__str__())


class Purchase(SubscriptionItem):
    """An example purchase."""

    plan = models.ForeignKey(PricingPlan, on_delete=models.CASCADE)
    """The pricing plan for the purchase."""

    for_organization = models.ForeignKey('Organization', null=True, related_name='for_purchase', on_delete=models.CASCADE)
    """The organization for which the purchase was initiated.
    
    Don't mess :attr:`for_organization` with :attr:`organization`!"""

    def __repr__(self):
        return "<Purchase: %s>" % (("pk=%d" % self.pk) if self.pk else "no pk")


class Organization(models.Model):
    """An example organization."""

    name = models.CharField(max_length=255)
    """Organization name."""

    purchase = models.OneToOneField(Purchase, on_delete=models.CASCADE)
    """The current active :class:`~debits.debits_test.models.Purchase` for the organization."""

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Organization: %s, %s>" % ((("pk=%d" % self.pk) if self.pk else "no pk"), self.__str__())
