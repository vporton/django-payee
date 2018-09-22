_Both simplify the logic of integrating your Python/Django backend with PayPal
(and in the future of other payment processors, too)
and support advanced payment features._

Accepting payments (currently we support only PayPal).

The engine is very advanced and supports regular and subscription payments.
For more details, see
[the wiki at GitHub.com](https://github.com/vporton/django-debits/wiki).

The program is in beta testing stage.

# Install

## Automatically

Type `pip install django-debits` (in your Python environment).

## Manually

Copy `debits/debits_base` and `debits/paypal` into your Django application.

Add `'debits.debits_base'` and `'debits.paypal'` to your `INSTALLED_APPS`.

## Last steps

After manual or automatic install chdir to the project directory and run:

```
python manage.py makemigrations
python manage.py migrate
python manage.py loaddata debits/debits_base/fixtures/*.json
```

# Usage

See
[the wiki at GitHub.com](https://github.com/vporton/django-debits/wiki)
and example code in `debits/debits_test`.

# Documentation & Features

* [The wiki](https://github.com/vporton/django-debits/wiki)
* [API docs](https://django-debits.readthedocs.io/en/latest/)

# Commercial version

This package is available under AGPL (you must publish the source of any your
software which uses this)
and under a commercial license ($40 currently, for any commercial software).

Pay $40 and you receive the commercial license (for one version of the software).
[Pay now.](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=K6MJJ3LHQLJS2)
For details of the license, see `LICENSE` file in the source.