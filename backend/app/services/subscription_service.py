"""Razorpay subscriptions. Browser callbacks never grant unverified credits."""
import hashlib
import hmac
import json
import re
import httpx
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import now
from app.services import billing_service as billing


def credentials_configured():
    s = get_settings()
    return bool(s.razorpay_key_id and s.razorpay_key_secret
                and s.razorpay_key_id.startswith('rzp_' + s.razorpay_mode + '_')
                and (s.razorpay_mode == 'test' or s.razorpay_live_enabled))


def configured():
    return bool(credentials_configured() and get_settings().razorpay_webhook_secret and plans())


def plans():
    try:
        values = json.loads(get_settings().razorpay_plans_json)
        if not isinstance(values, dict):
            raise ValueError()
        for key, value in values.items():
            if not re.fullmatch(r'[a-z0-9_-]{1,40}', key) or not re.fullmatch(r'plan_[A-Za-z0-9]+', value['plan_id']):
                raise ValueError()
            if type(value['credits']) is not int or not 1 <= value['credits'] <= 100000:
                raise ValueError()
            if not isinstance(value['name'], str) or not 1 <= len(value['name']) <= 100:
                raise ValueError()
        return values
    except (ValueError, TypeError, KeyError):
        raise AppError('Configure RAZORPAY_PLANS_JSON with name, plan_id and credits for each plan.', 503, 'billing_configuration') from None


def api(method, path, body=None):
    if not credentials_configured():
        raise AppError('Razorpay checkout is waiting for matching API keys and payment mode.', 503, 'billing_configuration')
    s = get_settings()
    try:
        result = httpx.request(method, 'https://api.razorpay.com/v1/' + path, json=body,
            auth=(s.razorpay_key_id, s.razorpay_key_secret), timeout=20, follow_redirects=False, trust_env=False)
        if not result.is_success:
            raise AppError('Razorpay rejected the request. Check the provider dashboard and configured plan.', 502, 'billing_provider')
        return result.json()
    except (httpx.HTTPError, ValueError):
        raise AppError('Razorpay response is unavailable. Reconcile this checkout before creating another subscription.', 502, 'billing_provider') from None


def account_key(actor):
    return get_settings().razorpay_mode + ':' + actor


def public(record):
    return {key: record.get(key) for key in ('provider_id', 'status', 'plan_key', 'plan_name', 'credits', 'amount', 'currency', 'period', 'interval', 'current_end', 'cancel_at_cycle_end', 'error')}


def start(store, actor, plan_key, request_id):
    if actor.get('local'):
        raise AppError('Sign in to an account before opening subscription checkout.', 403)
    selected = plans().get(plan_key)
    if not selected:
        raise AppError('Choose an available subscription plan.', 404)
    remote_plan = api('GET', 'plans/' + selected['plan_id'])
    item = remote_plan.get('item', {})
    if item.get('currency') != 'INR' or not isinstance(item.get('amount'), int) or item['amount'] <= 0:
        raise AppError('This checkout requires a positive INR subscription plan.', 409)
    key = account_key(actor['id'])
    old = store.db.subscriptions.find_one({'_id': key})
    if old and old.get('status') == 'created' and old.get('plan_key') == plan_key and old.get('provider_id'):
        return old
    if old and old.get('request_id') == request_id:
        if old.get('plan_key') != plan_key:
            raise AppError('This request already belongs to another plan.', 409)
        if old.get('provider_id'):
            return old
        raise AppError('Subscription creation is awaiting reconciliation. Refresh its status.', 409)
    query = {'_id': key, 'status': {'$in': ['cancelled', 'completed', 'expired']}}
    row = {'actor': actor['id'], 'mode': get_settings().razorpay_mode, 'request_id': request_id,
           'plan_key': plan_key, 'plan_id': selected['plan_id'], 'plan_name': selected['name'],
           'credits': selected['credits'], 'amount': item['amount'], 'currency': 'INR',
           'period': remote_plan['period'], 'interval': remote_plan['interval'],
           'status': 'creating', 'created_at': now()}
    try:
        if old:
            saved = store.db.subscriptions.find_one_and_replace(query, {'_id': key, **row}, return_document=ReturnDocument.AFTER)
            if not saved:
                raise AppError('An existing subscription or checkout is pending. Manage it before choosing another plan.', 409)
        else:
            store.db.subscriptions.insert_one({'_id': key, **row})
        # A separate immutable order binds later webhooks even after plan changes.
        order_id = hashlib.sha256((key + ':' + request_id).encode()).hexdigest()
        store.db.subscription_orders.insert_one({'_id': order_id, **row})
        remote = api('POST', 'subscriptions', {'plan_id': row['plan_id'], 'total_count': 12,
            'quantity': 1, 'customer_notify': 1, 'notes': {'shift_order': order_id}})
        if not re.fullmatch(r'sub_[A-Za-z0-9]+', remote.get('id', '')):
            raise AppError('Razorpay returned an invalid subscription identity.', 502)
        values = {'provider_id': remote['id'], 'status': remote['status'], 'updated_at': now()}
        store.db.subscription_orders.update_one({'_id': order_id}, {'$set': values})
        store.db.subscriptions.update_one({'_id': key, 'request_id': request_id}, {'$set': values})
        return {**row, **values}
    except DuplicateKeyError:
        raise AppError('A checkout already exists. Refresh its status.', 409) from None


def sync(store, remote):
    order_id = (remote.get('notes') or {}).get('shift_order')
    order = store.db.subscription_orders.find_one({'_id': order_id, 'mode': get_settings().razorpay_mode}) if isinstance(order_id, str) else None
    if not order or order['plan_id'] != remote.get('plan_id'):
        raise AppError('Subscription does not match a local checkout.', 409)
    values = {'provider_id': remote['id'], 'status': remote['status'], 'current_end': remote.get('current_end'),
              'updated_at': now(), 'error': None}
    store.db.subscription_orders.update_one({'_id': order['_id']}, {'$set': values})
    store.db.subscriptions.update_one({'_id': account_key(order['actor']), 'request_id': order['request_id']}, {'$set': values})
    return {**order, **values}


def credit_payment(store, order, payment):
    # Mandate authorization alone is not a paid billing cycle.
    if payment.get('status') != 'captured' or not payment.get('invoice_id'):
        return False
    invoice = api('GET', 'invoices/' + payment['invoice_id'])
    if invoice.get('subscription_id') != order['provider_id'] or invoice.get('payment_id') != payment['id']:
        raise AppError('Payment invoice does not match the subscription.', 409)
    if invoice.get('status') != 'paid' or payment.get('currency') != order['currency'] or payment.get('amount', 0) < order['amount']:
        return False
    if payment.get('amount_refunded', 0):
        return False
    key = 'razorpay:' + order['mode'] + ':' + payment['id']
    billing.grant(store, order['actor'], key, order['credits'])
    store.db.subscription_payments.update_one({'_id': key}, {'$setOnInsert': {
        'actor': order['actor'], 'subscription_id': order['provider_id'], 'invoice_id': invoice['id'],
        'credits': order['credits'], 'amount': payment['amount'], 'currency': payment['currency'], 'created_at': now()}}, upsert=True)
    return True


def refresh(store, actor):
    row = store.db.subscriptions.find_one({'_id': account_key(actor)})
    if not row:
        raise AppError('No subscription exists for this account.', 404)
    if not row.get('provider_id'):
        order_id = hashlib.sha256((account_key(actor) + ':' + row['request_id']).encode()).hexdigest()
        for skip in range(0, 500, 100):
            page = api('GET', f'subscriptions?count=100&skip={skip}')
            match = next((item for item in page.get('items', []) if (item.get('notes') or {}).get('shift_order') == order_id), None)
            if match:
                row = sync(store, match)
                break
            if len(page.get('items', [])) < 100:
                break
        if not row.get('provider_id'):
            raise AppError('Creation is still unconfirmed. Check Razorpay before retrying; no second subscription was created.', 409)
    row = sync(store, api('GET', 'subscriptions/' + row['provider_id']))
    # Reconcile missed webhooks without granting on a browser success message.
    invoices = api('GET', 'invoices?subscription_id=' + row['provider_id'] + '&count=100')
    for invoice in invoices.get('items', []):
        if invoice.get('status') == 'paid' and invoice.get('payment_id'):
            credit_payment(store, row, api('GET', 'payments/' + invoice['payment_id']))
    return row


def webhook(store, raw, signature):
    secret = get_settings().razorpay_webhook_secret
    if not credentials_configured() or not secret or not hmac.compare_digest(hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), signature):
        raise AppError('Webhook signature is invalid.', 400)
    try:
        event = json.loads(raw)
        payment = event.get('payload', {}).get('payment', {}).get('entity', {})
        if event.get('event') == 'payment.captured' and re.fullmatch(r'pay_[A-Za-z0-9]+', payment.get('id', '')):
            from app.services.credit_checkout import reconcile_payment
            reconcile_payment(store, api('GET', 'payments/' + payment['id']))
            return {'received': True}
        if event.get('event') == 'order.paid':
            from app.services.credit_checkout import reconcile_payment
            oid = event.get('payload', {}).get('order', {}).get('entity', {}).get('id', '')
            # Settlement can arrive before the create response is saved. Payment
            # reconciliation recovers the account binding from the fetched order.
            if re.fullmatch(r'order_[A-Za-z0-9]+', oid):
                for item in api('GET', 'orders/' + oid + '/payments').get('items', []):
                    reconcile_payment(store, api('GET', 'payments/' + item['id']))
            return {'received': True}
        subscription = event.get('payload', {}).get('subscription', {}).get('entity', {})
        sid = subscription.get('id', '')
        if not re.fullmatch(r'sub_[A-Za-z0-9]+', sid):
            return {'received': True}
        # Fetch current state so delayed events cannot undo a later cancellation.
        current = api('GET', 'subscriptions/' + sid)
        order_id = (current.get('notes') or {}).get('shift_order')
        if not isinstance(order_id, str) or not store.db.subscription_orders.find_one({'_id': order_id, 'mode': get_settings().razorpay_mode}):
            return {'received': True}
        row = sync(store, current)
        payment = event.get('payload', {}).get('payment', {}).get('entity', {})
        if event.get('event') == 'subscription.charged' and re.fullmatch(r'pay_[A-Za-z0-9]+', payment.get('id', '')):
            credit_payment(store, row, api('GET', 'payments/' + payment['id']))
        return {'received': True}
    except (ValueError, TypeError, AttributeError):
        raise AppError('Invalid webhook payload.', 400) from None
