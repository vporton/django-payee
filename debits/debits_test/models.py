from django.db import models
from debits.debits_base.models import Period, Product, BaseTransaction, SubscriptionItem, SimpleItem


class PricingPlan(models.Model):
    product = models.ForeignKey(Product)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    period = Period()

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<PricingPlan: %s, %s>" % ((("pk=%d" % self.pk) if self.pk else "no pk"), self.__str__())


class Purchase(models.Model):
    plan = models.ForeignKey(PricingPlan)
    item = models.OneToOneField(SubscriptionItem)
    # Don't mess .for_organization with .organization!
    for_organization = models.ForeignKey('Organization', null=True, related_name='for_purchase')

    def __repr__(self):
        return "<Purchase: %s>" % (("pk=%d" % self.pk) if self.pk else "no pk")


# proxy model
class MySubscriptionItem(SubscriptionItem):
    def __str__(self):
        return self.product.name + ' - ' + self.purchase.plan.name


class Organization(models.Model):
    name = models.CharField(max_length=255)
    purchase = models.OneToOneField(Purchase)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Organization: %s, %s>" % ((("pk=%d" % self.pk) if self.pk else "no pk"), self.__str__())
