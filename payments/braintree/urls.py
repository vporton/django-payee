from django.conf.urls import url
import payments.braintree.views

# FIXME
urlpatterns = [
    url(r'^ipn$', payments.braintree.views.ipn_view),
    url(r'^lcn$', payments.braintree.views.lcn_view),
]
