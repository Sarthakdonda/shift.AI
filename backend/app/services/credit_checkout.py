"""One-time credit purchases using server-priced, account-bound Razorpay Orders."""
import hashlib
import re
from pymongo.errors import DuplicateKeyError
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import now
from app.services import subscription_service as provider, billing_service as billing


def configured():
    s = get_settings()
    return bool(s.razorpay_credit_packs_enabled and provider.credentials_configured()
                and s.razorpay_credit_pack_amount >= s.razorpay_minimum_amount * 100)


def pack():
    s = get_settings()
    return {'name': 'Starter credits', 'amount': s.razorpay_credit_pack_amount,
            'credits': s.razorpay_credit_pack_credits, 'currency': s.razorpay_currency}


def public(row):
    return {key: row.get(key) for key in ('provider_id', 'name', 'amount', 'currency', 'credits', 'status', 'created_at', 'credited_at', 'request_id')}


def accept_order(store, row, remote):
    if row.get('provider_id') and row['provider_id'] != remote.get('id'):
        raise AppError('This purchase is already bound to a different payment order.', 409)
    if not re.fullmatch(r'order_[A-Za-z0-9]+', remote.get('id', '')) or remote.get('receipt') != row['receipt'] or remote.get('amount') != row['amount'] or remote.get('currency') != row['currency']:
        raise AppError('Razorpay order does not match the saved purchase.', 409)
    values = {'provider_id': remote['id'], 'updated_at': now()}
    # A delayed create response must never undo webhook settlement.
    saved = store.db.credit_purchases.update_one({'_id': row['_id'], '$or': [
        {'provider_id': {'$exists': False}}, {'provider_id': remote['id']}]}, {'$set': values})
    if not saved.matched_count:
        raise AppError('This purchase already has another payment order.', 409)
    store.db.credit_purchases.update_one({'_id': row['_id'], 'status': 'creating'}, {'$set': {'status': 'pending'}})
    return store.db.credit_purchases.find_one({'_id': row['_id']})


def recover_order(store, row):
    if row.get('provider_id'):
        return row
    # A receipt is unique to this actor and request. Never blindly repeat POST.
    for skip in range(0, 500, 100):
        page = provider.api('GET', f'orders?receipt={row["receipt"]}&count=100&skip={skip}')
        match = next((o for o in page.get('items', []) if o.get('receipt') == row['receipt']), None)
        if match:
            return accept_order(store, row, match)
        if len(page.get('items', [])) < 100:
            break
    raise AppError('Order creation is unconfirmed. Refresh payment status before starting another purchase.', 409, 'payment_pending')


def start(store, actor, request_id, quoted_amount, quoted_credits):
    if actor.get('local'):
        raise AppError('Sign in to an account before buying credits.', 403)
    if not configured():
        raise AppError('One-time credit checkout is not configured.', 503, 'billing_configuration')
    mode = get_settings().razorpay_mode
    identity = hashlib.sha256((mode + ':' + actor['id'] + ':' + request_id).encode()).hexdigest()
    row = store.db.credit_purchases.find_one({'_id': identity})
    if row:
        if row['amount'] != quoted_amount or row['credits'] != quoted_credits:
            raise AppError('This purchase request already has different terms.', 409)
        return recover_order(store, row)
    terms = pack()
    if terms['amount'] != quoted_amount or terms['credits'] != quoted_credits:
        raise AppError('The credit price changed. Refresh and review the current offer.', 409)
    row = {'_id': identity, 'actor': actor['id'], 'mode': mode, 'request_id': request_id,
           'receipt': 'shift_' + identity[:32], **terms, 'status': 'creating', 'created_at': now()}
    try:
        store.db.credit_purchases.insert_one(row)
    except DuplicateKeyError:
        return recover_order(store, store.db.credit_purchases.find_one({'_id': identity}))
    remote = provider.api('POST', 'orders', {'amount': row['amount'], 'currency': row['currency'],
        'receipt': row['receipt'], 'partial_payment': False, 'notes': {'shift_purchase': identity}})
    return accept_order(store, row, remote)


def reconcile_payment(store, payment):
    oid = payment.get('order_id', '')
    if not re.fullmatch(r'order_[A-Za-z0-9]+', oid):
        return False
    mode = get_settings().razorpay_mode
    row = store.db.credit_purchases.find_one({'provider_id': oid, 'mode': mode})
    remote = provider.api('GET', 'orders/' + oid)
    if not row:
        identity = (remote.get('notes') or {}).get('shift_purchase')
        row = store.db.credit_purchases.find_one({'_id': identity, 'mode': mode}) if isinstance(identity, str) else None
        if not row:
            return False
        row = accept_order(store, row, remote)
    if not re.fullmatch(r'pay_[A-Za-z0-9]+', payment.get('id', '')):
        raise AppError('Invalid payment identity.', 409)
    if payment.get('status') != 'captured' or payment.get('amount_refunded', 0):
        return False
    if payment.get('amount') != row['amount'] or payment.get('currency') != row['currency']:
        raise AppError('Payment amount or currency does not match this purchase.', 409)
    accept_order(store, row, remote)
    if remote.get('status') != 'paid' or remote.get('amount_paid') != row['amount'] or remote.get('amount_due') != 0:
        return False
    # One grant per ORDER, even if multiple payment events arrive concurrently.
    billing.grant(store, row['actor'], 'razorpay-order:' + mode + ':' + oid, row['credits'])
    store.db.credit_purchases.update_one({'_id': row['_id']}, {'$set': {'status': 'paid', 'payment_id': payment['id'], 'credited_at': now()}})
    return True


def refresh(store, actor, request_id):
    identity = hashlib.sha256((get_settings().razorpay_mode + ':' + actor + ':' + request_id).encode()).hexdigest()
    row = store.db.credit_purchases.find_one({'_id': identity, 'actor': actor})
    if not row:
        raise AppError('Purchase not found.', 404)
    row = recover_order(store, row)
    for item in provider.api('GET', 'orders/' + row['provider_id'] + '/payments').get('items', []):
        reconcile_payment(store, provider.api('GET', 'payments/' + item['id']))
    return store.db.credit_purchases.find_one({'_id': identity})
