# import datetime
# import hmac
# from urllib.parse import unquote
# from django.http import HttpResponse
import payee.payee_base
from django.conf import settings

# User settings.AVANGATE_SECRET

# FIXME: Don't allow to activate blocked accounts

# TODO: atomic transactions


# FIXME
def ipn_process_product(request, index, purchase):
    POST = request.POST

    recurring = purchase.pk in POST.getlist('IPN_LICENSE_PROD[]')
    if purchase.product.pk != int(POST.getlist('IPN_PID[]')[index]) or \
                    POST.getlist('IPN_PRICE[]')[index] != purchase.price or \
                    recurring != purchase.recurring or \
                    POST['CURRENCY'] != 'USD':
        purchase.blocked = True
        purchase.active = False
        purchase.save()
        return

    purchase.subscription_reference = POST.getlist('IPN_LICENSE_REF[]')[index]  # FIXME: which index: in IPN_PID[] or in IPN_LICENSE_PROD[]?

    if not purchase.first_payment.timestamp():
        purchase.first_payment = parse_date(POST['COMPLETE_DATE'])
    purchase.last_payment = parse_date(POST['COMPLETE_DATE'])

    purchase.active = True
    purchase.save()


# FIXME
def ipn_view(request):
    POST = request.POST

    if POST['ORDERSTATUS'] == 'COMPLETE':  # FIXME
        bundle_id = int(POST['REFNOEXT']) # FIXME
        try:
            bundle = payee.payee_base.Transaction.objects.get(pk=bundle_id)
            i = 0
            for purchase in bundle.purchase_set.order_by('id'):
                ipn_process_product(request, i, purchase)
                i += 1
        except payee.payee_base.Transaction.DoesNotExist:
            pass

    # FIXME
    return HttpResponse('<EPAYMENT>%s|%s</EPAYMENT>' % (date_for_hash, result_hash), content_type="text/plain")


def lcn_view(request):
    POST = request.POST

    try:
        purchase = payee.payee_base.Purchase.objects.get(subscription_reference=POST['LICENSE_CODE'])  # FIXME

        purchase.email = POST['EMAIL']  # FIXME
        purchase.first_payment = parse_date(POST['DATE_UPDATED'])  # FIXME
        purchase.last_payment = parse_date(POST['DATE_UPDATED'])  # FIXME
        purchase.active = FIXME

        purchase.save()
    except payee.payee_base.Purchase.DoesNotExist:
        pass  # TODO: Alert of hackers

    # FIXME
    return HttpResponse('<EPAYMENT>%s|%s</EPAYMENT>' % (date_for_hash, result_hash), content_type="text/plain")
