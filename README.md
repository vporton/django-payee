_Simplify the logic of integrating your Python/Django backend with PayPal
(and in the future of other payment processors, too)._

Accepting payments (currently we support only PayPal).

This program is available under AGPL and under a commercial license ($40 currently).

The program is in beta testing stage, use at your own risk.

The engine is very advanced and supports regular and subscription payments.
For more details, see
[the wiki at GitHub.com](https://github.com/vporton/django-debits/wiki).

# Install

## Automatically

Type `pip install django-debits` (in your Python environment).

## Manually

Copy `debits/debits_base` and `debits/paypal` into your Django application.

Add `'debits.debits_base'` to your `INSTALLED_APPS`.

# Usage

See
[the wiki at GitHub.com](https://github.com/vporton/django-debits/wiki)
and example code in `debits/debits_test`.

# Documentation & Features

See
[the wiki at GitHub.com](https://github.com/vporton/django-debits/wiki).