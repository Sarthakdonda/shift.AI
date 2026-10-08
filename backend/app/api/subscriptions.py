import hashlib
import hmac
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from app.core.auth import user
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import get_store
from app.services import subscription_service as service
from app.services import credit_checkout
from app.services import billing_service as billing
from app.services import pricing_catalog as pricing

router = APIRouter(prefix='/api/billing', tags=['Subscriptions'])


class Checkout(BaseModel):
    plan: str = Field(min_length=1, max_length=40)
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')


class Verification(BaseModel):
    razorpay_payment_id: str = Field(pattern=r'^pay_[A-Za-z0-9]+$')
    razorpay_subscription_id: str = Field(pattern=r'^sub_[A-Za-z0-9]+$')
    razorpay_signature: str = Field(pattern=r'^[0-9a-f]{64}$')


@router.get('/subscriptions')
def overview(account=Depends(user)):
    s = get_store()
    row = s.db.subscriptions.find_one({'_id': service.account_key(account['id'])})
    subscription = service.public(row) if row else None
    plans = service.plans()
    configured = service.configured()
    return {'mode': get_settings().razorpay_mode, 'configured': configured,
        'orders_enabled': credit_checkout.configured(), 'credit_pack': credit_checkout.pack(),
        'balance': billing.account(s, account['id'])['balance'], 'build_cost': billing.policy(s)['build_cost'],
        'purchases': [credit_checkout.public(r) for r in s.db.credit_purchases.find({'actor': account['id'], 'mode': get_settings().razorpay_mode}).sort('created_at', -1).limit(20)],
        'plans': [{'id': key, 'name': value['name'], 'credits': value['credits']} for key, value in plans.items()],
        'catalog': pricing.overview(plans, subscription, configured),
        'subscription': subscription}


@router.post('/checkout')
def checkout(body: Checkout, account=Depends(user)):
    row = service.start(get_store(), account, body.plan, body.request_id)
    return {**service.public(row), 'key_id': get_settings().razorpay_key_id, 'mode': get_settings().razorpay_mode, 'business_name': get_settings().razorpay_business_name}


class PurchaseRequest(BaseModel):
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')


class CreditCheckout(PurchaseRequest):
    quoted_amount: int = Field(ge=100)
    quoted_credits: int = Field(ge=1)


class CreditVerification(BaseModel):
    razorpay_payment_id: str = Field(pattern=r'^pay_[A-Za-z0-9]+$')
    razorpay_order_id: str = Field(pattern=r'^order_[A-Za-z0-9]+$')
    razorpay_signature: str = Field(pattern=r'^[0-9a-f]{64}$')


@router.post('/credits/checkout')
def buy_credits(body: CreditCheckout, request: Request, account=Depends(user)):
    from app.core.auth import limit_auth
    limit_auth(request, 'credit-checkout:' + account['id'])
    row = credit_checkout.start(get_store(), account, body.request_id, body.quoted_amount, body.quoted_credits)
    return {**credit_checkout.public(row), 'key_id': get_settings().razorpay_key_id,
            'business_name': get_settings().razorpay_business_name, 'mode': get_settings().razorpay_mode}


@router.post('/credits/verify')
def verify_credits(body: CreditVerification, account=Depends(user)):
    store = get_store()
    row = store.db.credit_purchases.find_one({'provider_id': body.razorpay_order_id,
        'actor': account['id'], 'mode': get_settings().razorpay_mode})
    if not row:
        raise AppError('Payment order does not belong to this account.', 403)
    if not service.credentials_configured():
        raise AppError('Razorpay credentials are unavailable.', 503, 'billing_configuration')
    expected = hmac.new(get_settings().razorpay_key_secret.encode(),
        (row['provider_id'] + '|' + body.razorpay_payment_id).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise AppError('Payment signature could not be verified.', 400)
    payment = service.api('GET', 'payments/' + body.razorpay_payment_id)
    if payment.get('order_id') != row['provider_id']:
        raise AppError('Payment does not match this order.', 409)
    credit_checkout.reconcile_payment(store, payment)
    return credit_checkout.public(store.db.credit_purchases.find_one({'_id': row['_id']}))


@router.post('/credits/refresh')
def refresh_credits(body: PurchaseRequest, request: Request, account=Depends(user)):
    from app.core.auth import limit_auth
    limit_auth(request, 'credit-refresh:' + account['id'])
    return credit_checkout.public(credit_checkout.refresh(get_store(), account['id'], body.request_id))


@router.post('/verify')
def verify(body: Verification, account=Depends(user)):
    store = get_store()
    row = store.db.subscriptions.find_one({'_id': service.account_key(account['id'])})
    if not row or row.get('provider_id') != body.razorpay_subscription_id:
        raise AppError('Subscription does not belong to this account.', 403)
    expected = hmac.new(get_settings().razorpay_key_secret.encode(),
        (body.razorpay_payment_id + '|' + row['provider_id']).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise AppError('Checkout signature could not be verified.', 400)
    return service.public(service.refresh(store, account['id']))


@router.post('/subscriptions/refresh')
def refresh(account=Depends(user)):
    return service.public(service.refresh(get_store(), account['id']))


@router.post('/subscriptions/cancel')
def cancel(account=Depends(user)):
    store = get_store()
    row = store.db.subscriptions.find_one({'_id': service.account_key(account['id'])})
    if not row or not row.get('provider_id'):
        raise AppError('No confirmed subscription exists.', 404)
    result = service.api('POST', 'subscriptions/' + row['provider_id'] + '/cancel', {'cancel_at_cycle_end': 1})
    service.sync(store, result)
    store.db.subscriptions.update_one({'_id': row['_id']}, {'$set': {'cancel_at_cycle_end': True}})
    return {'ok': True}


@router.post('/razorpay/webhook')
async def webhook(request: Request):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 256000:
            raise AppError('Webhook payload too large.', 413)
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(service.webhook, get_store(), bytes(raw), request.headers.get('x-razorpay-signature', ''))
