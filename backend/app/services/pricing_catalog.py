"""Single source of truth for subscription pricing, features, comparison and FAQ.

The catalog is data, not UI: the pricing page renders whatever this returns, so no
component duplicates a price. `SUBSCRIPTION_CATALOG_JSON` replaces the built-in
default and is validated before use.

Display price and checkout are deliberately separate. A tier period is purchasable
only when its `plan_key` exists in `RAZORPAY_PLANS_JSON` and subscription checkout
is configured; otherwise it is reported as unavailable instead of being presented
as a working purchase. The recurring amount actually charged is always the amount
Razorpay shows on its own authorization screen, and credits are granted only after
a paid cycle is confirmed server-side.
"""
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.core.config import get_settings
from app.core.errors import AppError

# Razorpay subscription states that mean the account really is on a paid tier.
ACTIVE_STATES = ('authenticated', 'active', 'pending', 'halted', 'charged')


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Feature(Strict):
    label: str = Field(min_length=1, max_length=140)
    included: bool = True


class Price(Strict):
    """`amount` is in the smallest currency unit, matching the rest of billing."""
    amount: int = Field(ge=0, le=100000000)
    credits: int = Field(ge=0, le=1000000)
    plan_key: str = Field(default='', max_length=40)


class Period(Strict):
    id: str = Field(pattern=r'^[a-z][a-z0-9_]{1,15}$')
    label: str = Field(min_length=1, max_length=40)
    months: int = Field(ge=1, le=36)
    suffix: str = Field(min_length=1, max_length=24)


class Tier(Strict):
    id: str = Field(pattern=r'^[a-z][a-z0-9_]{1,23}$')
    name: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=200)
    badge: str = Field(default='', max_length=30)
    highlight: bool = False
    free: bool = False
    contact_email: str = Field(default='', max_length=120)
    features: list[Feature] = Field(min_length=1, max_length=16)
    prices: dict[str, Price]


class Row(Strict):
    """A `yes`/`no` value renders as an icon; any other value renders as text."""
    label: str = Field(min_length=1, max_length=90)
    detail: str = Field(default='', max_length=140)
    values: dict[str, str]


class Question(Strict):
    question: str = Field(min_length=4, max_length=160)
    answer: str = Field(min_length=4, max_length=700)


class Catalog(Strict):
    currency: Literal['INR'] = 'INR'
    heading: str = Field(min_length=1, max_length=80)
    subheading: str = Field(min_length=1, max_length=260)
    periods: list[Period] = Field(min_length=1, max_length=4)
    tiers: list[Tier] = Field(min_length=1, max_length=4)
    comparison: list[Row] = Field(default_factory=list, max_length=24)
    comparison_note: str = Field(default='', max_length=300)
    faq: list[Question] = Field(default_factory=list, max_length=12)


DEFAULT = {
    'currency': 'INR',
    'heading': 'Choose your plan',
    'subheading': 'Start free, then keep credits arriving every cycle. Every plan includes the full '
                  'evidence-led workflow: adaptive discovery, analysis, Red Team review and deliverables.',
    'periods': [
        {'id': 'monthly', 'label': 'Monthly', 'months': 1, 'suffix': 'per month'},
        {'id': 'yearly', 'label': 'Yearly', 'months': 12, 'suffix': 'per year'},
    ],
    'tiers': [
        {
            'id': 'starter', 'name': 'Starter', 'free': True,
            'description': 'For one person taking a first problem from question to blueprint.',
            'features': [
                {'label': '100 starter credits, granted once'},
                {'label': 'Adaptive discovery, analysis, solution and blueprint'},
                {'label': 'Red Team review with up to three cycles'},
                {'label': 'Seven editable deliverables with Markdown, PDF and Office exports'},
                {'label': 'Evidence from PDF, DOCX, PPTX, XLSX, CSV and TXT files'},
                {'label': 'Credits renewed every billing cycle', 'included': False},
                {'label': 'Additional workspace members', 'included': False},
                {'label': 'Email support and payment invoices', 'included': False},
            ],
            'prices': {'monthly': {'amount': 0, 'credits': 100}, 'yearly': {'amount': 0, 'credits': 100}},
        },
        {
            'id': 'pro', 'name': 'Pro', 'badge': 'Most popular', 'highlight': True,
            'description': 'For professionals running several transformations every month.',
            'features': [
                {'label': '1,000 credits every paid cycle — about 100 validated application builds'},
                {'label': 'Everything in Starter, with credits that renew'},
                {'label': 'Up to 5 workspace members'},
                {'label': 'Approvals, version history and collaboration'},
                {'label': 'Email support within one business day'},
                {'label': 'Tax invoice for every payment'},
                {'label': 'Guided onboarding session', 'included': False},
            ],
            'prices': {
                'monthly': {'amount': 99900, 'credits': 1000, 'plan_key': 'pro_monthly'},
                'yearly': {'amount': 999000, 'credits': 1000, 'plan_key': 'pro_yearly'},
            },
        },
        {
            'id': 'business', 'name': 'Business',
            'description': 'For teams that need shared governance, approvals and seats.',
            'features': [
                {'label': '5,000 credits every paid cycle — about 500 validated application builds'},
                {'label': 'Everything in Pro'},
                {'label': 'Up to 25 workspace members'},
                {'label': 'Workspace roles, governance and readiness tracking'},
                {'label': 'Administration audit history'},
                {'label': 'Priority email support and a guided onboarding session'},
                {'label': 'Tax invoice for every payment'},
            ],
            'prices': {
                'monthly': {'amount': 399900, 'credits': 5000, 'plan_key': 'business_monthly'},
                'yearly': {'amount': 3999000, 'credits': 5000, 'plan_key': 'business_yearly'},
            },
        },
    ],
    'comparison': [
        {'label': 'Credits each billing cycle', 'detail': 'Granted after a cycle is paid and confirmed',
         'values': {'starter': '100 once', 'pro': '1,000', 'business': '5,000'}},
        {'label': 'Validated application builds', 'detail': '10 credits per build, refunded if validation fails',
         'values': {'starter': '10 total', 'pro': 'About 100', 'business': 'About 500'}},
        {'label': 'Projects', 'values': {'starter': 'Unlimited', 'pro': 'Unlimited', 'business': 'Unlimited'}},
        {'label': 'Workspace members', 'values': {'starter': '1', 'pro': '5', 'business': '25'}},
        {'label': 'Documents per project', 'values': {'starter': '20', 'pro': '20', 'business': '20'}},
        {'label': 'Red Team review cycles', 'values': {'starter': '3', 'pro': '3', 'business': '3'}},
        {'label': 'Editable deliverables', 'values': {'starter': '7', 'pro': '7', 'business': '7'}},
        {'label': 'Interface languages', 'values': {'starter': '20', 'pro': '20', 'business': '20'}},
        {'label': 'Approvals and governance', 'values': {'starter': 'yes', 'pro': 'yes', 'business': 'yes'}},
        {'label': 'Administration audit history', 'values': {'starter': 'no', 'pro': 'no', 'business': 'yes'}},
        {'label': 'Tax invoice for each payment', 'values': {'starter': 'no', 'pro': 'yes', 'business': 'yes'}},
        {'label': 'Support', 'values': {'starter': 'Documentation', 'pro': 'Email, one business day',
                                        'business': 'Priority email and onboarding'}},
        {'label': 'Cancel at the end of any cycle', 'values': {'starter': 'yes', 'pro': 'yes', 'business': 'yes'}},
    ],
    'comparison_note': 'Credit allowances are enforced by the credit ledger: every build reserves credits first and '
                       'refunds them when validation fails. Member and support allowances are commercial terms of the '
                       'plan rather than technical restrictions.',
    'faq': [
        {'question': 'Can I change my subscription later?',
         'answer': 'Yes. Cancel the current subscription at the end of its billing cycle, then choose another plan. '
                   'A second checkout cannot start while a subscription is still active, so the change takes effect '
                   'from the next cycle and you are never billed twice at once.'},
        {'question': 'Can I cancel my subscription anytime?',
         'answer': 'Yes. Cancellation is scheduled for the end of the current billing cycle, so you keep the access '
                   'and credits you have already paid for. Nothing is charged after that cycle ends.'},
        {'question': 'What happens when I upgrade?',
         'answer': 'Razorpay confirms the recurring amount and the mandate before you authorize anything. Credits are '
                   'added only after a billing cycle is actually paid and the invoice is verified on our server — '
                   'never because the browser reported success.'},
        {'question': 'What payment methods are accepted?',
         'answer': 'Whatever your Razorpay account supports for subscriptions, typically UPI autopay, cards and net '
                   'banking. Card and UPI details are entered inside Razorpay checkout; shift.AI never receives or '
                   'stores them.'},
        {'question': 'Will my subscription renew automatically?',
         'answer': 'Yes, through the mandate you authorize at checkout, for up to twelve cycles. Each paid cycle adds '
                   'that plan\u2019s credits exactly once, even if the confirmation arrives more than once.'},
        {'question': 'What happens when my subscription expires?',
         'answer': 'Credits already granted stay in your account and remain usable. Nothing new is added, and the '
                   'workspace returns to the free Starter allowance until you subscribe again.'},
        {'question': 'How is payment verified?',
         'answer': 'The checkout signature is verified server-side, then the payment is fetched again from Razorpay '
                   'and matched against the invoice and subscription. Signed webhook events reconcile anything the '
                   'browser misses, so a closed tab never loses a paid cycle.'},
    ],
}


def _raw():
    text = get_settings().subscription_catalog_json.strip()
    if not text:
        return DEFAULT
    try:
        return json.loads(text)
    except ValueError:
        raise AppError('SUBSCRIPTION_CATALOG_JSON is not valid JSON. Correct it, or remove it to use the built-in catalog.',
                       503, 'billing_configuration') from None


def definition() -> Catalog:
    try:
        model = Catalog.model_validate(_raw())
    except ValidationError:
        raise AppError('SUBSCRIPTION_CATALOG_JSON does not match the pricing catalog format. Correct it, or remove it to use the built-in catalog.',
                       503, 'billing_configuration') from None
    periods = [period.id for period in model.periods]
    if len(set(periods)) != len(periods):
        raise AppError('Each billing period in the pricing catalog needs a unique id.', 503, 'billing_configuration')
    tiers = [tier.id for tier in model.tiers]
    if len(set(tiers)) != len(tiers):
        raise AppError('Each pricing tier needs a unique id.', 503, 'billing_configuration')
    for tier in model.tiers:
        if set(tier.prices) != set(periods):
            raise AppError(f'Tier {tier.id} must price every billing period exactly once.', 503, 'billing_configuration')
    return model


def current(tiers, subscription):
    """The tier the account is actually on, from the confirmed subscription only."""
    if subscription and subscription.get('status') in ACTIVE_STATES and subscription.get('plan_key'):
        for tier in tiers:
            for period, price in tier['prices'].items():
                if price['plan_key'] and price['plan_key'] == subscription['plan_key']:
                    return tier['id'], period
    return next((tier['id'] for tier in tiers if tier['free']), tiers[0]['id']), None


def overview(plans, subscription, purchasable):
    """Catalog, per-period checkout availability, and the account's current tier.

    `plans` is the validated RAZORPAY_PLANS_JSON mapping and `purchasable` is
    whether subscription checkout is fully configured.
    """
    model = definition()
    tiers = []
    for tier in model.tiers:
        prices = {}
        for period in model.periods:
            price = tier.prices[period.id]
            mapped = plans.get(price.plan_key) if price.plan_key else None
            prices[period.id] = {
                'amount': price.amount,
                # Never advertise more credits than the mapped plan actually grants.
                'credits': mapped['credits'] if mapped else price.credits,
                'monthly_amount': round(price.amount / period.months),
                'plan_key': price.plan_key,
                'plan_name': mapped['name'] if mapped else '',
                'configured': bool(mapped),
                'available': bool(tier.free or (mapped and purchasable)),
            }
        tiers.append({**tier.model_dump(), 'prices': prices})
    tier_id, period_id = current(tiers, subscription)
    return {'currency': model.currency, 'heading': model.heading, 'subheading': model.subheading,
            'periods': [period.model_dump() for period in model.periods], 'tiers': tiers,
            'comparison': [row.model_dump() for row in model.comparison], 'comparison_note': model.comparison_note,
            'faq': [item.model_dump() for item in model.faq],
            'current_tier': tier_id, 'current_period': period_id}
