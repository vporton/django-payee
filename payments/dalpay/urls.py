from django.conf.urls import url
import payments.dalpay.views

# FIXME
urlpatterns = [
    url(r'^ipn$', payments.dalpay.views.ipn_view),
    url(r'^lcn$', payments.dalpay.views.lcn_view),
]
