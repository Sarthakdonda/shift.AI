"""Atomic single-document credit ledger: reservations, completion and refunds."""
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from app.core.errors import AppError
from app.repositories.store import now
from app.core.config import get_settings
from datetime import timedelta

BUILD_COST = 10
PLANS = [{'id': 'starter', 'name': 'Starter', 'included_credits': 100, 'price': None,
          'description': '100 evaluation credits. A validated application build costs 10 credits; failed or unvalidated builds cost 0.'}]


def policy(store):
    return store.db.builder_plans.find_one({'_id': 'default'}, {'_id': 0}) or {
        'name': 'Starter', 'build_cost': get_settings().builder_build_cost,
        'initial_credits': get_settings().builder_initial_credits, 'max_entities': 20}


def account(store, actor):
    try:
        store.db.credit_accounts.update_one({'_id': actor}, {'$setOnInsert': {
            'balance': policy(store)['initial_credits'], 'plan': 'starter', 'entries': [], 'created_at': now()}}, upsert=True)
    except DuplicateKeyError:
        pass
    return store.db.credit_accounts.find_one({'_id': actor})


def reserve(store, actor, key):
    account(store, actor)
    cost = policy(store)['build_cost']
    doc = store.db.credit_accounts.find_one_and_update(
        {'_id': actor, 'balance': {'$gte': cost}, 'entries.key': {'$ne': key}, 'entries.999': {'$exists': False}},
        {'$inc': {'balance': -cost}, '$push': {'entries': {
            'key': key, 'amount': -cost, 'status': 'reserved', 'created_at': now()}}},
        return_document=ReturnDocument.AFTER)
    if not doc:
        previous = store.db.credit_accounts.find_one({'_id': actor, 'entries.key': key})
        if previous:
            return False
        raise AppError('Insufficient credits or evaluation transaction limit reached. Contact your administrator.', 402)
    return True


def settle(store, actor, key, success):
    # Status predicate and credit adjustment happen together, including on retries.
    update = {'$set': {'entries.$.status': 'charged' if success else 'refunded', 'entries.$.finished_at': now()}}
    if not success:
        wallet = account(store, actor)
        entry = next((e for e in wallet['entries'] if e['key'] == key), None)
        if not entry:
            return
        update['$inc'] = {'balance': -entry['amount']}
    store.db.credit_accounts.update_one({'_id': actor, 'entries': {'$elemMatch': {'key': key, 'status': 'reserved'}}}, update)


def grant(store, actor, key, amount):
    wallet = account(store, actor)
    entry = next((e for e in wallet['entries'] if e['key'] == key), None)
    if entry and entry['amount'] != amount:
        raise AppError('This grant request ID belongs to a different amount.', 409)
    if entry:
        return
    result = store.db.credit_accounts.update_one({'_id': actor, 'entries.key': {'$ne': key}, 'entries.999': {'$exists': False}},
        {'$inc': {'balance': amount}, '$push': {'entries': {'key': key, 'amount': amount, 'status': 'grant', 'created_at': now()}}})
    if not result.modified_count:
        raise AppError('Credit history limit reached or grant was already processed.', 409)


def recover_orphans(store, actor):
    for entry in account(store, actor)['entries']:
        if entry['status'] != 'reserved' or entry['created_at'].replace(tzinfo=now().tzinfo) > now() - timedelta(minutes=35):
            continue
        if not store.db.application_builds.find_one({'billing_actor': actor, 'request_id': entry['key']}):
            settle(store, actor, entry['key'], False)
