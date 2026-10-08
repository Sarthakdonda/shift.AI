"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Script from "next/script";
import {
  ArrowRight,
  BadgeCheck,
  CreditCard,
  Info,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import { Shell } from "@/components/layout/shell";
import { T } from "@/components/locale";
import { Modal } from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/ui/feedback";
import { ErrorBox, Loading } from "@/components/ui/states";
import {
  Comparison,
  Faq,
  PeriodToggle,
  PlanCard,
  type PlanAction,
} from "@/components/billing/pricing";
import { api, post } from "@/lib/api";
import {
  money,
  subscriptionHeld,
  type BillingPeriod,
  type BillingState,
  type PlanPrice,
  type PlanTier,
  type Purchase,
  type Subscription,
} from "@/lib/billing";

type CheckoutResult = {
  razorpay_payment_id: string;
  razorpay_subscription_id?: string;
  razorpay_order_id?: string;
  razorpay_signature: string;
};
type CheckoutOptions = {
  key: string;
  subscription_id?: string;
  order_id?: string;
  amount?: number;
  currency?: string;
  name: string;
  description: string;
  retry?: { enabled: boolean };
  handler: (result: CheckoutResult) => void;
  modal: { ondismiss: () => void };
};
declare global {
  interface Window {
    Razorpay?: new (options: CheckoutOptions) => {
      open(): void;
      on(event: string, callback: () => void): void;
    };
  }
}

type Selection = { tier: PlanTier; price: PlanPrice; period: BillingPeriod };

export default function BillingPage() {
  const [data, setData] = useState<BillingState | null>(null);
  const [period, setPeriod] = useState("");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const plan = useRef<{ key: string; id: string } | null>(null);
  const pack = useRef<string | null>(null);

  const load = useCallback(async () => {
    const state = await api<BillingState>("/billing/subscriptions");
    setData(state);
    setPeriod(
      (current) =>
        current ||
        state.catalog.current_period ||
        state.catalog.periods[0]?.id ||
        "",
    );
  }, []);

  useEffect(() => {
    load()
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [load]);

  const refresh = useCallback(async () => {
    try {
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }, [load]);

  const catalog = data?.catalog;
  const active = useMemo(
    () => catalog?.periods.find((p) => p.id === period) || catalog?.periods[0],
    [catalog, period],
  );
  const held = subscriptionHeld(data?.subscription ?? null);

  function action(tier: PlanTier): PlanAction {
    const price = tier.prices[period];
    const current = tier.id === catalog?.current_tier;
    const label = `Upgrade to ${tier.name}`;
    if (current)
      return {
        current: true,
        label,
        hint: tier.free
          ? "Your free allowance. Upgrade whenever you need more credits."
          : `${price?.credits.toLocaleString()} credits are added on each paid cycle.`,
        disabled: true,
      };
    if (tier.free)
      return {
        current: false,
        label: "Manage subscription",
        hint: "Cancelling a paid plan returns this workspace to Starter at the end of the cycle.",
        disabled: !data?.subscription,
      };
    if (!price?.configured)
      return {
        current: false,
        label,
        hint: `${active?.label} billing is not enabled for this plan yet.`,
        disabled: true,
      };
    if (!data?.configured)
      return {
        current: false,
        label,
        hint: "Subscription checkout is waiting for payment configuration.",
        disabled: true,
      };
    if (held)
      return {
        current: false,
        label,
        hint: "Cancel your current subscription before switching plans.",
        disabled: true,
      };
    return {
      current: false,
      label,
      hint: ready
        ? `${price.credits.toLocaleString()} credits on every paid cycle.`
        : "Secure checkout is still loading…",
      disabled: busy || !ready,
    };
  }

  function select(tier: PlanTier) {
    setError("");
    setNotice("");
    const price = tier.prices[period];
    if (tier.free || !active) {
      document
        .getElementById("subscription")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    setSelection({ tier, price, period: active });
  }

  /** Razorpay authorizes the mandate; credits arrive only after server verification. */
  async function checkout(selected: Selection) {
    setSelection(null);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (!window.Razorpay)
        throw new Error("Checkout is still loading. Try again shortly.");
      const key = selected.price.plan_key;
      if (plan.current?.key !== key)
        plan.current = { key, id: crypto.randomUUID() };
      const order = await post<
        Subscription & { key_id: string; mode: string; business_name: string }
      >("/billing/checkout", { plan: key, request_id: plan.current.id });
      const popup = new window.Razorpay({
        key: order.key_id,
        subscription_id: order.provider_id!,
        name: order.business_name,
        description: `${order.plan_name} · ${order.credits} credits per paid cycle${order.mode === "test" ? " · TEST MODE" : ""}`,
        handler: async (result) => {
          try {
            await post("/billing/verify", result);
            plan.current = null;
            await load();
            setNotice(
              "Checkout verified. Credits are added once Razorpay confirms a paid billing cycle.",
            );
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        },
        modal: {
          ondismiss: () => {
            setBusy(false);
            setNotice("Checkout closed. Nothing has been charged.");
            void refresh();
          },
        },
      });
      popup.on("payment.failed", () => {
        setBusy(false);
        setError(
          "Payment did not complete. Refresh the subscription status below before retrying.",
        );
      });
      popup.open();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  async function manage(path: string, done: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await post(path);
      await load();
      setNotice(done);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function buyCredits() {
    if (!data || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (!window.Razorpay)
        throw new Error("Checkout is still loading. Try again shortly.");
      pack.current ||= crypto.randomUUID();
      const order = await post<
        Purchase & { key_id: string; business_name: string }
      >("/billing/credits/checkout", {
        request_id: pack.current,
        quoted_amount: data.credit_pack.amount,
        quoted_credits: data.credit_pack.credits,
      });
      if (order.status === "paid") {
        pack.current = null;
        await load();
        setNotice("This purchase was already credited to your account.");
        setBusy(false);
        return;
      }
      const popup = new window.Razorpay({
        key: order.key_id,
        order_id: order.provider_id,
        amount: order.amount,
        currency: order.currency,
        name: order.business_name,
        description: `${order.credits} credits · one-time purchase`,
        retry: { enabled: false },
        handler: async (result) => {
          try {
            const verified = await post<Purchase>(
              "/billing/credits/verify",
              result,
            );
            pack.current = null;
            await load();
            setNotice(
              verified.status === "paid"
                ? `${verified.credits} credits added to your account.`
                : "Payment is awaiting capture. Refresh the payment status below shortly.",
            );
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        },
        modal: {
          ondismiss: () => {
            setBusy(false);
            setNotice("Checkout closed. Nothing has been charged.");
            void refresh();
          },
        },
      });
      popup.on("payment.failed", () => {
        pack.current = null;
        setBusy(false);
        setError(
          "Payment failed. Start a new checkout, or refresh a pending purchase below.",
        );
      });
      popup.open();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
      await refresh();
    }
  }

  async function refreshPurchase(requestId: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const purchase = await post<Purchase>("/billing/credits/refresh", {
        request_id: requestId,
      });
      await load();
      setNotice(
        purchase.status === "paid"
          ? "Payment confirmed and credits added."
          : "No captured payment is confirmed yet, so no credits have been added.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (loading)
    return (
      <Shell>
        <Loading label="Loading your subscription…" />
      </Shell>
    );
  if (!data || !catalog || !active)
    return (
      <Shell>
        <ErrorBox
          message={error || "Billing is unavailable right now."}
          onRetry={() => void refresh()}
        />
      </Shell>
    );

  const subscription = data.subscription;
  const checkoutLoadable = data.configured || data.orders_enabled;

  return (
    <Shell>
      {checkoutLoadable && (
        <Script
          src="https://checkout.razorpay.com/v1/checkout.js"
          onReady={() => setReady(true)}
          onError={() =>
            setError("Razorpay checkout could not load. Please try again.")
          }
        />
      )}

      <div className="pb-page">
        <header className="pb-head">
          <span className="eyebrow">
            <T text={"PLANS & BILLING"} />
          </span>
          <h1>{catalog.heading}</h1>
          <p>{catalog.subheading}</p>
          <div className="pb-head-meta">
            <span className="badge">
              <Wallet size={12} aria-hidden />
              {`${data.balance.toLocaleString()} credits available`}
            </span>
            <span className="badge">
              <ShieldCheck size={12} aria-hidden />
              <T text={"Payments verified on the server"} />
            </span>
            {data.mode === "test" && (
              <span className="badge badge-orange">
                <T text={"Razorpay test mode · no real money is charged"} />
              </span>
            )}
          </div>
        </header>

        {error && <ErrorBox message={error} />}
        {notice && (
          <p className="notice" role="status">
            <BadgeCheck size={17} aria-hidden />
            {notice}
          </p>
        )}

        <PeriodToggle catalog={catalog} value={period} onChange={setPeriod} />

        <div className="pb-grid">
          {catalog.tiers.map((tier) => (
            <PlanCard
              key={tier.id}
              tier={tier}
              period={active}
              catalog={catalog}
              action={action(tier)}
              onSelect={() => select(tier)}
            />
          ))}
        </div>

        {!data.configured && (
          <p className="setup-note">
            <Info size={16} aria-hidden />
            <span>
              <T
                text={
                  "Recurring checkout activates once Razorpay subscription plans and a webhook secret are configured for this workspace. Prices above are the published plan terms."
                }
              />
            </span>
          </p>
        )}

        <section className="panel pb-manage" id="subscription">
          <div className="section-toolbar" style={{ margin: 0 }}>
            <div>
              <h2>
                <T text={"Your subscription"} />
              </h2>
              <p className="muted">
                <T
                  text={
                    "Credits are granted only after Razorpay confirms a paid billing cycle."
                  }
                />
              </p>
            </div>
            {subscription && (
              <div className="toolbar-controls">
                <button
                  type="button"
                  className="button button-secondary button-sm"
                  disabled={busy || !data.configured}
                  onClick={() =>
                    void manage(
                      "/billing/subscriptions/refresh",
                      "Subscription status reconciled with Razorpay.",
                    )
                  }
                >
                  {busy ? (
                    <LoaderCircle size={14} className="spin" />
                  ) : (
                    <RefreshCw size={14} />
                  )}
                  <T text={"Refresh status"} />
                </button>
                <button
                  type="button"
                  className="button button-secondary button-sm"
                  disabled={
                    busy ||
                    !data.configured ||
                    !subscription.provider_id ||
                    subscription.cancel_at_cycle_end ||
                    ["cancelled", "completed", "expired"].includes(
                      subscription.status,
                    )
                  }
                  onClick={() => setCancelling(true)}
                >
                  <T text={"Cancel at cycle end"} />
                </button>
              </div>
            )}
          </div>

          {subscription ? (
            <div className="pb-manage-grid">
              <div className="pb-stat">
                <small>
                  <T text={"Plan"} />
                </small>
                <strong>{subscription.plan_name}</strong>
              </div>
              <div className="pb-stat">
                <small>
                  <T text={"Status"} />
                </small>
                <strong>
                  {subscription.status}
                  {subscription.cancel_at_cycle_end
                    ? " · ending at cycle end"
                    : ""}
                </strong>
              </div>
              <div className="pb-stat">
                <small>
                  <T text={"Recurring amount"} />
                </small>
                <strong>
                  {`${money(subscription.amount, subscription.currency)} / ${subscription.interval} ${subscription.period}`}
                </strong>
              </div>
              <div className="pb-stat">
                <small>
                  <T text={"Credits per paid cycle"} />
                </small>
                <strong>{subscription.credits.toLocaleString()}</strong>
              </div>
            </div>
          ) : (
            <p className="muted">
              <T
                text={
                  "No subscription is active. This workspace is on the free Starter allowance."
                }
              />
            </p>
          )}
        </section>

        {data.orders_enabled && (
          <section className="warm-panel">
            <span className="eyebrow">
              <T text={"ONE-TIME TOP-UP"} />
            </span>
            <h3>{data.credit_pack.name}</h3>
            <p>
              {`${money(data.credit_pack.amount, data.credit_pack.currency)} for ${data.credit_pack.credits} credits — a single purchase with no subscription or automatic renewal. Each validated application build costs ${data.build_cost} credits.`}
            </p>
            <button
              type="button"
              className="button button-dark"
              style={{ marginTop: 16 }}
              disabled={busy || !ready}
              onClick={() => void buyCredits()}
            >
              {busy ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <CreditCard size={16} />
              )}
              {`Buy ${data.credit_pack.credits} credits${data.mode === "test" ? " · test payment" : ""}`}
            </button>
          </section>
        )}

        {!!data.purchases.length && (
          <section className="panel">
            <h2>
              <T text={"Credit purchases"} />
            </h2>
            {data.purchases.map((purchase) => (
              <div className="pb-purchase" key={purchase.request_id}>
                <div>
                  <strong>
                    {`${money(purchase.amount, purchase.currency)} · ${purchase.credits} credits`}
                  </strong>
                  <small>
                    {purchase.status === "paid"
                      ? "Paid and credited"
                      : "Awaiting payment confirmation"}
                  </small>
                </div>
                {purchase.status === "paid" ? (
                  <span className="badge badge-green">
                    <T text={"Credited"} />
                  </span>
                ) : (
                  <button
                    type="button"
                    className="button button-secondary button-sm"
                    disabled={busy}
                    onClick={() => void refreshPurchase(purchase.request_id)}
                  >
                    <RefreshCw size={14} />
                    <T text={"Refresh payment status"} />
                  </button>
                )}
              </div>
            ))}
          </section>
        )}

        <section>
          <div className="section-toolbar">
            <div>
              <h2>
                <T text={"Compare every plan"} />
              </h2>
              <p className="muted">
                <T
                  text={
                    "What each plan includes, and the allowances that differ."
                  }
                />
              </p>
            </div>
          </div>
          <Comparison
            tiers={catalog.tiers}
            rows={catalog.comparison}
            note={catalog.comparison_note}
          />
        </section>

        <Faq items={catalog.faq} />
      </div>

      <Modal
        open={!!selection}
        onOpenChange={(open) => !open && setSelection(null)}
        title="Review your subscription"
        description="Razorpay confirms the recurring amount and mandate on its own screen before you authorize anything."
        icon={<CreditCard size={22} />}
      >
        {selection && (
          <>
            <div className="pb-summary">
              <div className="pb-summary-row">
                <span>
                  <T text={"Plan"} />
                </span>
                <strong>{selection.tier.name}</strong>
              </div>
              <div className="pb-summary-row">
                <span>
                  <T text={"Billing period"} />
                </span>
                <strong>{selection.period.label}</strong>
              </div>
              <div className="pb-summary-row">
                <span>
                  <T text={"Credits per paid cycle"} />
                </span>
                <strong>{selection.price.credits.toLocaleString()}</strong>
              </div>
              <div className="pb-summary-row">
                <span>
                  <T text={"Renews"} />
                </span>
                <strong>
                  <T text={"Automatically, up to 12 cycles"} />
                </strong>
              </div>
              <div className="pb-summary-row pb-summary-total">
                <span>
                  <T text={"Due each cycle"} />
                </span>
                <strong>
                  {money(selection.price.amount, catalog.currency)}
                </strong>
              </div>
            </div>
            <p className="muted small" style={{ marginTop: 12 }}>
              <T
                text={
                  "Credits are added after a paid cycle is verified on our server. Cancel at any time to stop future cycles."
                }
              />
            </p>
            <div className="modal-actions">
              <button
                data-dialog-cancel
                type="button"
                className="button button-secondary"
                onClick={() => setSelection(null)}
              >
                <T text={"Back to plans"} />
              </button>
              <button
                type="button"
                className="button button-primary"
                disabled={busy}
                onClick={() => void checkout(selection)}
              >
                <T text={"Continue to payment"} />
                <ArrowRight size={16} />
              </button>
            </div>
          </>
        )}
      </Modal>

      <ConfirmDialog
        open={cancelling}
        onOpenChange={setCancelling}
        title="Cancel at the end of this cycle?"
        description="You keep the credits and access already paid for. Nothing is charged after the current billing cycle ends."
        confirmLabel="Schedule cancellation"
        danger
        onConfirm={() =>
          manage(
            "/billing/subscriptions/cancel",
            "Cancellation scheduled for the end of the current billing cycle.",
          )
        }
      />
    </Shell>
  );
}
