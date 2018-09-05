import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

SECRET_KEY = 'Eech4Ak6Iedah1ahahMaeng4mahsee7Z'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'debits.debits_base',
    'debits.paypal',
    'debits.debits_test',
]

MIDDLEWARE = [
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'obican', 'templates'),
                os.path.join(BASE_DIR, 'core', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

ROOT_URLCONF = 'debits.debits_test.urls'

# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

## Payments settings

#PAYMENTS_HOST = 'XXX'
#IPN_HOST = 'XXX'
#FROM_EMAIL = 'XXX'
PROLONG_PAYMENT_VIEW = 'transaction-prolong-payment'
PAYMENTS_DAYS_BEFORE_DUE_REMIND = 10
PAYMENTS_DAYS_BEFORE_TRIAL_END_REMIND = 10
#PAYPAL_EMAIL = 'XXX'
#PAYPAL_ID = 'XXX' #PayPal account ID
# https://developer.paypal.com/developer/applications
#PAYPAL_CLIENT_ID = 'XXX'
#PAYPAL_SECRET = 'XXX'
PAYPAL_DEBUG = True
PAYMENTS_REALM = 'testapp1'

try:
    from local_settings import *
except ImportError as e:
    pass
