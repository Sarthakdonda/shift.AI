"use client";
import { useCallback, useEffect, useState } from "react";
import { Shell } from "@/components/layout/shell";
import { api, post } from "@/lib/api";
import styles from "@/components/application/builder.module.css";

type Plan = { name: string; build_cost: number; initial_credits: number; max_entities: number };
type Data = { plan: Plan; accounts: { id: string; balance: number }[]; builds: { id: string; project_id: string; status: string }[]; deployments: { id: string; project_id: string; status: string }[] };
export default function BuilderAdmin() {
  const [data, setData] = useState<Data | null>(null), [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState(""), [busy, setBusy] = useState(false), [notice, setNotice] = useState("");
  const [account, setAccount] = useState(""), [amount, setAmount] = useState(100);
  const load = useCallback(async () => { const result = await api<Data>("/builder/admin"); setData(result); setPlan(result.plan); }, []);
  useEffect(() => { load().catch(error => setError(error.message)); }, [load]);
  async function run(operation: () => Promise<unknown>) { setBusy(true); setError(""); setNotice(""); try { await operation(); await load(); setNotice("Saved."); } catch (error) { setError((error as Error).message); } finally { setBusy(false); } }
  return <Shell><div className={styles.builder}><h1>Generation administration</h1><p>Platform access is enforced by the backend. Workspace membership alone does not grant billing administration.</p>
    {error && <p className={styles.error} role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {data && plan && <><form className={styles.panel} onSubmit={event => { event.preventDefault(); void run(() => post("/builder/admin/plan", plan)); }}><h2>Plan policy</h2><p>New account credits apply only to newly created credit accounts. Existing balances and transaction amounts remain intact. Live subscriptions and payments are not enabled.</p>
      <label>Plan name<input required value={plan.name} onChange={event => setPlan({ ...plan, name: event.target.value })}/></label>
      {([['build_cost', 'Credits per validated build', 0, 10000], ['initial_credits', 'Starting credits', 0, 100000], ['max_entities', 'Maximum modules', 1, 20]] as const).map(([key, label, min, max]) => <label key={key}>{label}<input type="number" min={min} max={max} required value={plan[key]} onChange={event => setPlan({ ...plan, [key]: Number(event.target.value) })}/></label>)}<button disabled={busy}>Save policy</button></form>
      <form className={styles.panel} onSubmit={event => { event.preventDefault(); void run(() => post("/builder/admin/credits", { account_id: account, amount, request_id: crypto.randomUUID() })); }}><h2>Grant credits</h2><label>Account ID<input required value={account} onChange={event => setAccount(event.target.value)}/></label><label>Credits<input type="number" required min={1} max={100000} value={amount} onChange={event => setAmount(Number(event.target.value))}/></label><button disabled={busy}>Grant credits</button><details><summary>Account balances</summary>{data.accounts.map(item => <p key={item.id}><code>{item.id}</code> · {item.balance} credits</p>)}</details></form>
      {([['Builds', data.builds], ['Deployments', data.deployments]] as const).map(([title, items]) => <section className={styles.panel} key={title}><h2>{title}</h2>{items.length ? items.map(item => <p key={item.id}><a href={`/project/${item.project_id}/application`}>{item.project_id}</a> · {item.status}</p>) : <p>No activity.</p>}</section>)}
    </>}
  </div></Shell>;
}
