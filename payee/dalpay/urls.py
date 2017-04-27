from django.conf.urls import url
import payee.dalpay.views

# FIXME
urlpatterns = [
    url(r'^ipn$', payee.dalpay.views.ipn_view),
    url(r'^lcn$', payee.dalpay.views.lcn_view),
]
