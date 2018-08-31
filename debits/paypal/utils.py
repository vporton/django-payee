from dateutil.relativedelta import relativedelta

from debits.debits_base.base import Period


class PayPalUtils(object):
    @staticmethod
    def calculate_date(date, offset):
        delta = {
            Period.UNIT_DAYS: lambda: relativedelta(days=offset.count),
            Period.UNIT_WEEKS: lambda: relativedelta(weeks=offset.count),
            Period.UNIT_MONTHS: lambda: relativedelta(months=offset.count),
            Period.UNIT_YEARS: lambda: relativedelta(years=offset.count),
        }[offset.unit]()
        new_date = date + delta
        if new_date.day != date.day:
            new_date += relativedelta(days=1)
        return new_date
