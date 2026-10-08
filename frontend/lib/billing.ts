/**
 * Subscription types and formatting for the pricing page.
 *
 * Every price, feature, comparison row and FAQ answer comes from
 * `GET /api/billing/subscriptions`, so nothing here hardcodes an amount.
 */

export type BillingPeriod = {
  id: string;
  label: string;
  months: number;
  suffix: string;
};

export type PlanFeature = { label: string; included: boolean };

/** `amount` and `monthly_amount` are in the smallest currency unit (paise). */
export type PlanPrice = {
  amount: number;
  credits: number;
  monthly_amount: number;
  plan_key: string;
  plan_name: string;
  configured: boolean;
  available: boolean;
};

export type PlanTier = {
  id: string;
  name: string;
  description: string;
  badge: string;
  highlight: boolean;
  free: boolean;
  contact_email: string;
  features: PlanFeature[];
  prices: Record<string, PlanPrice>;
};

export type ComparisonRow = {
  label: string;
  detail: string;
  values: Record<string, string>;
};

export type FaqEntry = { question: string; answer: string };

export type PricingCatalog = {
  currency: string;
  heading: string;
  subheading: string;
  periods: BillingPeriod[];
  tiers: PlanTier[];
  comparison: ComparisonRow[];
  comparison_note: string;
  faq: FaqEntry[];
  current_tier: string;
  current_period: string | null;
};

export type Subscription = {
  provider_id?: string;
  status: string;
  plan_key?: string;
  plan_name: string;
  credits: number;
  amount: number;
  currency: string;
  period: string;
  interval: number;
  current_end?: number | null;
  cancel_at_cycle_end?: boolean;
};

export type Purchase = {
  provider_id?: string;
  name: string;
  amount: number;
  currency: string;
  credits: number;
  status: string;
  request_id: string;
  created_at: string;
};

export type CreditPack = {
  name: string;
  amount: number;
  currency: string;
  credits: number;
};

export type BillingState = {
  mode: string;
  configured: boolean;
  orders_enabled: boolean;
  credit_pack: CreditPack;
  balance: number;
  build_cost: number;
  purchases: Purchase[];
  plans: { id: string; name: string; credits: number }[];
  catalog: PricingCatalog;
  subscription: Subscription | null;
};

/** Razorpay states in which a new checkout must not be started. */
const HELD = [
  "creating",
  "created",
  "authenticated",
  "active",
  "pending",
  "halted",
  "charged",
];

export const subscriptionHeld = (subscription: Subscription | null) =>
  !!subscription && HELD.includes(subscription.status);

/** Smallest currency unit to a localized amount, without inventing decimals. */
export function money(amount: number, currency = "INR") {
  const value = amount / 100;
  const whole = Number.isInteger(value);
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(value);
}

export const shortestPeriod = (periods: BillingPeriod[]) =>
  periods.reduce(
    (shortest, period) =>
      period.months < shortest.months ? period : shortest,
    periods[0],
  );

/** Percentage saved against paying the shortest period repeatedly. */
export function savingsPercent(
  tier: PlanTier,
  period: BillingPeriod,
  base: BillingPeriod,
) {
  if (!base || base.id === period.id) return 0;
  const chosen = tier.prices[period.id];
  const reference = tier.prices[base.id];
  if (!chosen?.amount || !reference?.amount) return 0;
  const full = reference.amount * (period.months / base.months);
  return full > chosen.amount
    ? Math.round(((full - chosen.amount) / full) * 100)
    : 0;
}

/** Best saving any tier offers for a period, used to label the toggle. */
export const bestSavings = (
  tiers: PlanTier[],
  period: BillingPeriod,
  base: BillingPeriod,
) =>
  tiers.reduce(
    (best, tier) => Math.max(best, savingsPercent(tier, period, base)),
    0,
  );
