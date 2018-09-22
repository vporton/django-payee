import logging
from composite_field import CompositeField
from dateutil.relativedelta import relativedelta
from django.db import models
from django.utils.translation import ugettext_lazy as _


logger = logging.getLogger('debits')
"""The logger used by Debits."""


class Period(CompositeField):
    """Period (for example of recurring payment or of a trial subscription).

    It may be expressed in days, weeks, months, or years. Several units cannot be mixed:
    for example, it cannot be 2 months and 13 days."""
    UNIT_DAYS = 1
    UNIT_WEEKS = 2
    UNIT_MONTHS = 3
    UNIT_YEARS = 4

    period_choices = ((UNIT_DAYS, _("days")),  # different processors may support a part of it
                      (UNIT_WEEKS, _("weeks")),
                      (UNIT_MONTHS, _("months")),
                      (UNIT_YEARS, _("years")))
    """For Django :class:`~django.forms.ChoiceField`."""

    unit = models.SmallIntegerField()
    """days, weeks, months, or years."""

    count = models.SmallIntegerField()
    """The number of the units"""

    def __init__(self, unit=None, count=None):
        super().__init__()
        if unit is not None:
            self['unit'].default = unit
        if count is not None:
            self['count'].default = count


# The following functions do not work as a method, because
# CompositeField is replaced with composite_field.base.CompositeField.Proxy:

def period_to_string(period):
    """Human readable description of a period.

    Args:
        period: `Period` field.

    Returns:
        A human readable string."""
    hash = {e[0]: e[1] for e in Period.period_choices}
    return "%d %s" % (period.count, hash[period.unit])


def period_to_delta(period):
    """Convert :class:`Period` to :class:`relativedelta`."""
    return {
        Period.UNIT_DAYS: lambda: relativedelta(days=period.count),
        Period.UNIT_WEEKS: lambda: relativedelta(weeks=period.count),
        Period.UNIT_MONTHS: lambda: relativedelta(months=period.count),
        Period.UNIT_YEARS: lambda: relativedelta(years=period.count),
    }[period.unit]()
