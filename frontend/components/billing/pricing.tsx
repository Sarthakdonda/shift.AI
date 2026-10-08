"use client";

import { Check, Minus, Plus, ArrowRight, Mail, Sparkles } from "lucide-react";
import { T } from "@/components/locale";
import {
  bestSavings,
  money,
  savingsPercent,
  shortestPeriod,
  type BillingPeriod,
  type ComparisonRow,
  type FaqEntry,
  type PlanTier,
  type PricingCatalog,
} from "@/lib/billing";

/** Monthly / yearly switch. Changing it re-prices every card from the catalog. */
export function PeriodToggle({
  catalog,
  value,
  onChange,
}: {
  catalog: PricingCatalog;
  value: string;
  onChange: (id: string) => void;
}) {
  const base = shortestPeriod(catalog.periods);
  return (
    <div className="pb-toggle-row">
      <div
        className="pb-toggle"
        role="group"
        aria-label="Billing period"
      >
        {catalog.periods.map((period) => {
          const saving = bestSavings(catalog.tiers, period, base);
          return (
            <button
              key={period.id}
              type="button"
              aria-pressed={value === period.id}
              onClick={() => onChange(period.id)}
            >
              <span className="pb-toggle-dot" aria-hidden />
              {period.label}
              {saving > 0 && (
                <span className="badge badge-orange">{`Save ${saving}%`}</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function FeatureList({ features }: { features: PlanTier["features"] }) {
  return (
    <ul className="pb-features">
      {features.map((feature) => (
        <li
          key={feature.label}
          className={feature.included ? "" : "is-excluded"}
        >
          {feature.included ? (
            <Check size={15} aria-label="Included" />
          ) : (
            <Minus size={15} aria-label="Not included" />
          )}
          <span>{feature.label}</span>
        </li>
      ))}
    </ul>
  );
}

export type PlanAction = {
  /** Rendered instead of a button when the account is already on this tier. */
  current: boolean;
  label: string;
  hint: string;
  disabled: boolean;
};

export function PlanCard({
  tier,
  period,
  catalog,
  action,
  onSelect,
}: {
  tier: PlanTier;
  period: BillingPeriod;
  catalog: PricingCatalog;
  action: PlanAction;
  onSelect: () => void;
}) {
  const price = tier.prices[period.id];
  const base = shortestPeriod(catalog.periods);
  const saving = savingsPercent(tier, period, base);
  const classes = [
    "pb-card",
    tier.highlight ? "is-featured" : "",
    action.current ? "is-current" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <section className={classes} aria-labelledby={`plan-${tier.id}`}>
      <div className="pb-card-top">
        <h2 id={`plan-${tier.id}`}>{tier.name}</h2>
        {tier.badge && (
          <span className="badge badge-orange">
            <Sparkles size={12} aria-hidden />
            {tier.badge}
          </span>
        )}
      </div>

      <div>
        <p className="pb-price">
          <strong>
            {price.amount === 0 ? "Free" : money(price.amount, catalog.currency)}
          </strong>
          {price.amount > 0 && <span>{period.suffix}</span>}
        </p>
        <p className="pb-price-note">
          {price.amount === 0
            ? `${price.credits} credits included`
            : saving > 0
              ? `${money(price.monthly_amount, catalog.currency)} per month · save ${saving}%`
              : `${price.credits.toLocaleString()} credits each cycle`}
        </p>
      </div>

      <p className="pb-card-description">{tier.description}</p>

      {action.current ? (
        <p className="pb-card-status" role="status">
          <Check size={16} aria-hidden />
          <T text={"Current plan"} />
        </p>
      ) : tier.contact_email && !price.available ? (
        <a
          className="button button-secondary pb-card-cta"
          href={`mailto:${tier.contact_email}?subject=${encodeURIComponent(`${tier.name} plan enquiry`)}`}
        >
          <Mail size={16} aria-hidden />
          <T text={"Contact sales"} />
        </a>
      ) : (
        <button
          type="button"
          className={`button pb-card-cta ${tier.highlight ? "button-primary" : "button-dark"}`}
          disabled={action.disabled}
          onClick={onSelect}
        >
          {action.label}
          <ArrowRight size={16} aria-hidden />
        </button>
      )}
      <p className="pb-card-hint">{action.hint}</p>

      <FeatureList features={tier.features} />
    </section>
  );
}

function Mark({ value }: { value: string }) {
  if (value === "yes")
    return (
      <span className="pb-mark pb-mark-yes" title="Included">
        <Check size={13} aria-hidden />
        <span className="sr-only">Included</span>
      </span>
    );
  if (value === "no")
    return (
      <span className="pb-mark pb-mark-no" title="Not included">
        <Minus size={13} aria-hidden />
        <span className="sr-only">Not included</span>
      </span>
    );
  return <>{value}</>;
}

export function Comparison({
  tiers,
  rows,
  note,
}: {
  tiers: PlanTier[];
  rows: ComparisonRow[];
  note: string;
}) {
  if (!rows.length) return null;
  return (
    <div>
      <div className="pb-compare">
        <table>
          <caption className="sr-only">
            Feature comparison across subscription plans
          </caption>
          <thead>
            <tr>
              <th scope="col">
                <T text={"Included"} />
              </th>
              {tiers.map((tier) => (
                <th
                  key={tier.id}
                  scope="col"
                  className={tier.highlight ? "is-featured" : ""}
                  style={{ textAlign: "center" }}
                >
                  {tier.name}
                  {tier.badge && <span>{tier.badge}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <th scope="row">
                  {row.label}
                  {row.detail && <small>{row.detail}</small>}
                </th>
                {tiers.map((tier) => (
                  <td
                    key={tier.id}
                    className={tier.highlight ? "is-featured" : ""}
                  >
                    <Mark value={row.values[tier.id] ?? "no"} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {note && (
        <p className="muted small" style={{ marginTop: 14 }}>
          {note}
        </p>
      )}
    </div>
  );
}

export function Faq({ items }: { items: FaqEntry[] }) {
  if (!items.length) return null;
  return (
    <section className="pb-faq">
      <div className="pb-faq-intro">
        <span className="eyebrow">
          <T text={"BEFORE YOU SUBSCRIBE"} />
        </span>
        <h2 style={{ marginTop: 12 }}>
          <T text={"Subscription questions"} />
        </h2>
        <p>
          <T
            text={
              "How billing, renewal, cancellation and payment verification actually work in this workspace."
            }
          />
        </p>
      </div>
      <div className="pb-faq-list">
        {items.map((item) => (
          <details key={item.question}>
            <summary>
              <span>{item.question}</span>
              <Plus size={17} aria-hidden />
            </summary>
            <p className="pb-faq-answer">{item.answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
