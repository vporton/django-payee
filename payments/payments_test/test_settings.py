import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

SECRET_KEY = 'la5izaeKgei9YoGh'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'payments.payments_base',
    'payments.paypal',
    'payments.payments_test',
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

ROOT_URLCONF = 'payments.payments_test.urls'

# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

## Payments settings

PAYMENTS_HOST = 'http://portonvictor.org:9091'
IPN_HOST = 'http://portonvictor.org:9091'
FROM_EMAIL = 'admins@arcamens.com'
PROLONG_PAYMENT_VIEW = 'transaction-prolong-payment'
PAYMENTS_DAYS_BEFORE_DUE_REMIND = 10
PAYMENTS_DAYS_BEFORE_TRIAL_END_REMIND = 10
PAYPAL_EMAIL = 'paypal-sandbox-merchant@portonvictor.org'
PAYPAL_ID = 'CDA2QQH9TQ44C' #PayPal account ID
# https://developer.paypal.com/developer/applications
PAYPAL_CLIENT_ID = 'AVV1uyNk5YCJfDaDgUI9QwsYCtyEP8aFyMV7pCaiUn7Icuo8TYwaaXDM2nTV25wEGKHMl2CAeT4XD9BR'
PAYPAL_SECRET = 'EGIp5GUxqdDpK3zHulDL8NdD12uJzrKxbr78GnpAGYBQ9GfqiA2URabY0jrZzAI26n-S9z8EO2KwlZrN'
PAYPAL_DEBUG = True
PAYMENTS_REALM = 'testapp4'