import datetime
import hmac
from urllib.parse import unquote
from django.db import transaction
from django.http import HttpResponse
from django.views import View
import payee.payee_base
from payee.payee_base.processors import PaymentCallback
from payee.payee_base.models import Purchase
from django.conf import settings

# User settings.AVANGATE_SECRET

# FIXME: https://secure.avangate.com/order/upgrade.php?LICENSE=1234567 - https://developer.avangate.com/03JSON-RPC_API/Best_Practices/One_click_(1-click)_subscription_upgrade

# FIXME: Process chargebacks and refunds (necessary?)

# FIXME: Don't allow to activate blocked accounts

# TODO: atomic transactions


def dump_request(file, var):
    if settings.DEBUG:
        open(file, 'w+').write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ":\n" + var) + "\n\n"


# Internal
def parse_date(string):
    return datetime.datetime.strptime(string, '%Y-%m-%d %H:%M:%S')


# Internal
def add_prefix(string):
    if string == '': return ''  # https://developer.avangate.com/Webhooks/Instant_Payment_Notification_(IPN)
    string = string.encode('UTF-8')
    return str(len(string)) + string


def check_hackers(request):
    # request.POST does not support order, so do it manually
    equals = request.body.split('&')
    pairs = map(lambda string: string.split('=', 1), equals)
    values_for_hash = map(lambda pair: unquote(pair[1]), filter(lambda pair: pair[0] != 'HASH', pairs))
    hash_obj = hmac.new(settings.AVANGATE_SECRET.encode())
    for string in values_for_hash:
        hash_obj.update(add_prefix(string).encode())
    return hash_obj.hexdigest().lower() != request.POST['HASH'].lower()


class AvangateIPN(PaymentCallback, View):
    def post(self, request):
        dump_request("IPN.txt", request.POST)
        if check_hackers(request):
            return  # TODO: Alert of hackers

        POST = request.POST

        if POST['ORDERSTATUS'] == 'COMPLETE':
            bundle_id = int(POST['REFNOEXT'])
            try:
                bundle = payee.payee_base.Transaction.objects.get(pk=bundle_id)
                if float(POST['IPN_SHIPPING']) == bundle.shipping__sum:  # TODO: Alert of hackers
                    i = 0
                    for purchase_id in bundle.purchase_set.order_by('id').values_list('id', flat=True):
                        self.ipn_process_product(request, i, purchase_id)
                        i += 1
            except payee.payee_base.Transaction.DoesNotExist:
                pass

        date_for_hash = datetime.datetime().strftime('%Y%m%d%H%M%S')
        result_str_for_hash = add_prefix(POST['IPN_PID[]'][0]) + \
                              add_prefix(POST['IPN_PNAME[]'][0]) + \
                              add_prefix(POST['IPN_DATE']) + \
                              add_prefix(date_for_hash)
        result_hash = hmac.new(settings.AVANGATE_SECRET.encode(), result_str_for_hash.encode()).hex_digest()

        # POST['TEST_ORDER']  # TODO

        return HttpResponse('<EPAYMENT>%s|%s</EPAYMENT>' % (date_for_hash, result_hash), content_type="text/plain")

    def ipn_process_product(self, request, index, purchase_id):
        POST = request.POST

        with transaction.atomic(): # transaction to be sure we are really first
            purchase = Purchase.object.get(pk=purchase_id)

            first = not purchase.first_payment.timestamp()

            recurring = purchase.pk in POST.getlist('IPN_LICENSE_PROD[]')
            if purchase.product.pk != int(POST.getlist('IPN_PID[]')[index]) or \
                            POST.getlist('IPN_PRICE[]')[index] != purchase.price or \
                            recurring != purchase.recurring or \
                            POST['CURRENCY'] != 'USD':
                return

            if first:
                purchase.first_payment = parse_date(POST['COMPLETE_DATE'])
            purchase.last_payment = parse_date(POST['COMPLETE_DATE'])
            purchase.save()  # first time

        purchase.subscription_reference = POST.getlist('IPN_LICENSE_REF[]')[index]  # FIXME: which index: in IPN_PID[] or in IPN_LICENSE_PROD[]?

        purchase.active = True
        purchase.save()  # second time

        if first:
            self.on_payment(purchase)


class AvangateLCN(PaymentCallback, View):
    def post(self, request):
        dump_request("LCN.txt", request.POST)
        if check_hackers(request):
            return  # TODO: Alert of hackers

        POST = request.POST

        try:
            # It is not a problem if it happens before the first IPN request, because the first IPN request activates the purchase anyway
            # Transaction to be sure we are really first. I am paranoic to store correct first_payment.
            with transaction.atomic():
                purchase = payee.payee_base.Purchase.objects.get(subscription_reference=POST['LICENSE_CODE'])  # FIXME: correct?
                if not purchase.first_payment.timestamp():
                    purchase.first_payment = parse_date(POST['DATE_UPDATED'])
                purchase.last_payment = parse_date(POST['DATE_UPDATED'])
                purchase.email = POST['EMAIL']
                purchase.active = POST['DISABLED'] == '0' and \
                                  (POST['STATUS'] == 'ACTIVE' or POST['STATUS'] == 'PASTDUE') and \
                                  POST['EXPIRED'] != '1'
                purchase.save()
            if purchase.active:
                self.on_subscription_start(purchase)
            else:
                self.on_subscription_stop(purchase)
            # POST['TEST']  # TODO
        except payee.payee_base.Purchase.DoesNotExist:
            pass  # TODO: Alert of hackers

        date_for_hash = datetime.datetime().strftime('%Y%m%d%H%M%S')
        result_str_for_hash = add_prefix(POST['LICENSE_CODE']) + add_prefix(POST['EXPIRATION_DATE']) + add_prefix(date_for_hash)
        result_hash = hmac.new(settings.AVANGATE_SECRET.encode(), result_str_for_hash.encode()).hex_digest()

        return HttpResponse('<EPAYMENT>%s|%s</EPAYMENT>' % (date_for_hash, result_hash), content_type="text/plain")
