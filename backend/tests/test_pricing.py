"""Pricing catalog contracts: configurable data, honest availability, no invented checkout."""
import json
import pytest
from app.core.errors import AppError
from app.services import pricing_catalog as pricing

PLANS = {'pro_monthly': {'name': 'Pro monthly', 'plan_id': 'plan_A', 'credits': 1000},
         'pro_yearly': {'name': 'Pro yearly', 'plan_id': 'plan_B', 'credits': 1000}}


def tier(catalog, tier_id):
    return next(t for t in catalog['tiers'] if t['id'] == tier_id)


def test_default_catalog_prices_every_period_for_every_tier():
    catalog = pricing.overview({}, None, False)
    periods = [period['id'] for period in catalog['periods']]
    assert periods == ['monthly', 'yearly']
    assert [t['id'] for t in catalog['tiers']] == ['starter', 'pro', 'business']
    for entry in catalog['tiers']:
        assert set(entry['prices']) == set(periods)
        assert entry['features'] and all(f['label'] for f in entry['features'])
    assert sum(t['highlight'] for t in catalog['tiers']) == 1
    assert catalog['comparison'] and catalog['faq'] and catalog['comparison_note']
    # Comparison values cover every tier so no column renders as unknown.
    for row in catalog['comparison']:
        assert set(row['values']) == {t['id'] for t in catalog['tiers']}


def test_yearly_price_is_cheaper_per_month_and_reported_as_such():
    catalog = pricing.overview(PLANS, None, True)
    pro = tier(catalog, 'pro')
    assert pro['prices']['yearly']['monthly_amount'] < pro['prices']['monthly']['amount']
    assert pro['prices']['monthly']['monthly_amount'] == pro['prices']['monthly']['amount']


@pytest.mark.parametrize('purchasable', [True, False])
def test_unmapped_or_unconfigured_plans_are_never_offered_as_purchasable(purchasable):
    catalog = pricing.overview(PLANS, None, purchasable)
    pro = tier(catalog, 'pro')
    business = tier(catalog, 'business')
    assert pro['prices']['monthly']['configured'] is True
    assert pro['prices']['monthly']['available'] is purchasable
    # No Razorpay plan is mapped for Business, so it can never be bought.
    assert business['prices']['monthly']['configured'] is False
    assert business['prices']['monthly']['available'] is False
    # The free tier stays selectable without any payment configuration.
    assert tier(catalog, 'starter')['prices']['monthly']['available'] is True


def test_displayed_credits_match_the_mapped_plan_not_the_catalog():
    plans = {'pro_monthly': {'name': 'Pro monthly', 'plan_id': 'plan_A', 'credits': 250}}
    assert tier(pricing.overview(plans, None, True), 'pro')['prices']['monthly']['credits'] == 250


@pytest.mark.parametrize('status, expected', [('active', 'pro'), ('authenticated', 'pro'),
                                              ('cancelled', 'starter'), ('created', 'starter')])
def test_current_tier_follows_only_a_confirmed_subscription(status, expected):
    subscription = {'status': status, 'plan_key': 'pro_yearly'}
    catalog = pricing.overview(PLANS, subscription, True)
    assert catalog['current_tier'] == expected
    assert catalog['current_period'] == ('yearly' if expected == 'pro' else None)


def test_configured_catalog_replaces_the_default(setup, monkeypatch):
    custom = {'currency': 'INR', 'heading': 'Pick a plan', 'subheading': 'Only one tier exists here.',
              'periods': [{'id': 'monthly', 'label': 'Monthly', 'months': 1, 'suffix': 'per month'}],
              'tiers': [{'id': 'solo', 'name': 'Solo', 'description': 'One seat.', 'free': True,
                         'features': [{'label': 'Everything included'}],
                         'prices': {'monthly': {'amount': 0, 'credits': 25}}}],
              'comparison': [], 'faq': []}
    monkeypatch.setattr(setup[3], 'subscription_catalog_json', json.dumps(custom))
    catalog = pricing.overview({}, None, False)
    assert catalog['heading'] == 'Pick a plan'
    assert [t['id'] for t in catalog['tiers']] == ['solo']
    assert catalog['current_tier'] == 'solo'


@pytest.mark.parametrize('value', [
    'not json',
    '{"heading": "Missing the rest"}',
    json.dumps({'currency': 'INR', 'heading': 'H', 'subheading': 'S',
                'periods': [{'id': 'monthly', 'label': 'Monthly', 'months': 1, 'suffix': 'pm'},
                            {'id': 'yearly', 'label': 'Yearly', 'months': 12, 'suffix': 'py'}],
                'tiers': [{'id': 'solo', 'name': 'Solo', 'description': 'd', 'features': [{'label': 'f'}],
                           'prices': {'monthly': {'amount': 0, 'credits': 1}}}]}),
])
def test_broken_catalog_configuration_reports_a_coded_setup_error(setup, monkeypatch, value):
    monkeypatch.setattr(setup[3], 'subscription_catalog_json', value)
    with pytest.raises(AppError) as failure:
        pricing.definition()
    assert failure.value.status == 503 and failure.value.code == 'billing_configuration'


def test_overview_endpoint_publishes_the_catalog_and_balance(setup):
    client = setup[0]
    body = client.get('/api/billing/subscriptions').json()
    assert body['balance'] == 100 and body['build_cost'] == 10
    assert body['configured'] is False and body['subscription'] is None
    assert body['catalog']['current_tier'] == 'starter'
    assert [t['id'] for t in body['catalog']['tiers']] == ['starter', 'pro', 'business']
    # Nothing is presented as purchasable while payment credentials are absent.
    assert all(not price['available'] for entry in body['catalog']['tiers'] if not entry['free']
               for price in entry['prices'].values())
    assert 'plan_id' not in json.dumps(body) and 'secret' not in json.dumps(body).lower()
