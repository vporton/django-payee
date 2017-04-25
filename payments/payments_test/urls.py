from django.conf.urls import url
from .callbacks import MyPayPalIPN
from . import views

urlpatterns = [
    url(r'^$', views.list_organizations_view, name='list-organizations'),
    url(r'^pay$', views.purchase_view, name='do-purchase'),
    url(r'^create-organization$', views.create_organization_view, name='create-organization'),
    url(r'^transaction-prolong-payment/([0-9]+)$', views.transaction_payment_view, name='transaction-prolong-payment'),
    url(r'^organization-prolong-payment/([0-9]+)$', views.organization_payment_view, name='organization-prolong-payment'),
    url(r'^unsubscribe-organization/([0-9]+)$', views.unsubscribe_organization_view, name='unsubscribe-organization'),
    url(r'^paypal/ipn$', MyPayPalIPN.as_view(), name='paypal-ipn')
]
