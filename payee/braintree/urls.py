from django.conf.urls import url
import payee.braintree.views

# FIXME
urlpatterns = [
    url(r'^ipn$', payee.braintree.views.ipn_view),
    url(r'^lcn$', payee.braintree.views.lcn_view),
]
