import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api, formatApiError } from "@/lib/api";
import { formatPHP, humanAction, timeAgo } from "@/lib/admin";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from "@/components/ui/tabs";
import { ArrowLeft, Copy } from "lucide-react";
import { toast } from "sonner";

const STATUS_TONES = {
  active: "bg-emerald-100 text-emerald-800",
  invited: "bg-amber-100 text-amber-800",
  disabled: "bg-stone-200 text-stone-700",
};

function useAgent(id) {
  return useQuery({
    queryKey: ["admin-agent", id],
    queryFn: () => api.get(`/admin/agents/${id}`).then((r) => r.data.agent),
    enabled: !!id,
  });
}

function AdjustBalanceDialog({ agent, onDone }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState("credit");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.post(`/admin/agents/${agent.id}/adjust-balance`, {
        kind, amount, reason,
      });
      toast.success(`Balance ${kind}ed`);
      setOpen(false);
      setAmount(""); setReason(""); setKind("credit");
      onDone?.();
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button data-testid="admin-agent-adjust-balance-button">Adjust balance</Button>
      </DialogTrigger>
      <DialogContent data-testid="admin-agent-adjust-balance-dialog">
        <DialogHeader>
          <DialogTitle>Adjust booking balance</DialogTitle>
          <DialogDescription>
            Records a signed <span className="font-mono">ADJUSTMENT_*</span> transaction and an audit entry. A reason is required.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Direction</Label>
              <div className="grid grid-cols-2 rounded-lg border border-stone-200 bg-white p-1">
                {["credit", "debit"].map((k) => (
                  <button
                    key={k} type="button"
                    onClick={() => setKind(k)}
                    data-testid={`admin-agent-adjust-kind-${k}`}
                    className={[
                      "py-1.5 text-sm rounded-md capitalize",
                      kind === k ? "bg-stone-900 text-white" : "text-stone-600",
                    ].join(" ")}
                  >{k}</button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="amt">Amount (PHP)</Label>
              <Input id="amt" required type="number" step="0.01" min="0.01"
                value={amount} onChange={(e) => setAmount(e.target.value)}
                data-testid="admin-agent-adjust-amount-input" />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="rsn">Reason</Label>
            <Textarea id="rsn" rows={3} required minLength={3}
              value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. 'Manual credit for cash deposit received on 2026-09-27, ref DEP-0234'"
              data-testid="admin-agent-adjust-reason-input" />
          </div>
          {error ? (
            <Alert variant="destructive" data-testid="admin-agent-adjust-error">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          <DialogFooter>
            <Button type="submit" disabled={busy} data-testid="admin-agent-adjust-submit">
              {busy ? "Saving…" : `Confirm ${kind}`}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function TransactionsPanel({ agentId }) {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-agent-txns", agentId],
    queryFn: () => api.get(`/admin/agents/${agentId}/transactions`, { params: { page_size: 25 } }).then((r) => r.data),
    enabled: !!agentId,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Transactions</CardTitle>
        <CardDescription>Latest 25 ledger entries</CardDescription>
      </CardHeader>
      <CardContent className="p-0 overflow-x-auto">
        {isLoading ? (
          <div className="p-6 text-sm text-stone-500">Loading…</div>
        ) : !data?.transactions?.length ? (
          <div className="p-6 text-sm text-stone-500" data-testid="admin-agent-txns-empty">
            No transactions yet.
          </div>
        ) : (
          <table className="w-full text-sm min-w-[720px]" data-testid="admin-agent-txns-table">
            <thead className="border-b border-stone-200 bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-3 text-left">When</th>
                <th className="px-4 py-3 text-left">Type</th>
                <th className="px-4 py-3 text-left">Account</th>
                <th className="px-4 py-3 text-right">Amount</th>
                <th className="px-4 py-3 text-right">Balance after</th>
                <th className="px-4 py-3 text-left">Note</th>
              </tr>
            </thead>
            <tbody>
              {data.transactions.map((t) => {
                const positive = parseFloat(t.amount) >= 0;
                return (
                  <tr key={t.id} className="border-t border-stone-100">
                    <td className="px-4 py-3 text-xs text-stone-500 whitespace-nowrap">{timeAgo(t.created_at)}</td>
                    <td className="px-4 py-3">
                      <Badge variant="outline" className="font-mono text-[10px]">{t.type}</Badge>
                    </td>
                    <td className="px-4 py-3 capitalize text-stone-600">{t.account_kind}</td>
                    <td className={"px-4 py-3 text-right font-mono " + (positive ? "text-emerald-700" : "text-red-700")}>
                      {positive ? "+" : ""}{formatPHP(t.amount)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">{formatPHP(t.balance_after)}</td>
                    <td className="px-4 py-3 text-xs text-stone-500 max-w-[240px] truncate">{t.note || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function AuditPanel({ agentId }) {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-agent-audit", agentId],
    queryFn: () => api.get(`/admin/agents/${agentId}/audit-logs`).then((r) => r.data),
    enabled: !!agentId,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Audit trail</CardTitle>
        <CardDescription>Every admin action on this agent</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="p-6 text-sm text-stone-500">Loading…</div>
        ) : !data?.audit_logs?.length ? (
          <div className="p-6 text-sm text-stone-500">Nothing yet.</div>
        ) : (
          <ul className="divide-y divide-stone-100" data-testid="admin-agent-audit-list">
            {data.audit_logs.map((e) => (
              <li key={e.id} className="flex items-start justify-between gap-4 px-6 py-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium">{humanAction(e.action)}</div>
                  {e.after ? (
                    <div className="text-xs text-stone-500 truncate">
                      {Object.entries(e.after).map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · ")}
                    </div>
                  ) : null}
                </div>
                <div className="text-[10px] uppercase tracking-widest text-stone-400 shrink-0">
                  {timeAgo(e.created_at)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ProfileForm({ agent, onSaved }) {
  const [form, setForm] = useState({
    display_name: agent.display_name || "",
    agency_name: agent.agency_name || "",
    phone: agent.phone || "",
    address: agent.address || "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.patch(`/admin/agents/${agent.id}`, form);
      toast.success("Profile updated");
      onSaved?.();
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="space-y-4" data-testid="admin-agent-profile-form">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2"><Label>Display name</Label>
          <Input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            data-testid="admin-agent-profile-name-input" /></div>
        <div className="space-y-2"><Label>Agency</Label>
          <Input value={form.agency_name} onChange={(e) => setForm({ ...form, agency_name: e.target.value })}
            data-testid="admin-agent-profile-agency-input" /></div>
        <div className="space-y-2"><Label>Phone</Label>
          <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}
            data-testid="admin-agent-profile-phone-input" /></div>
        <div className="space-y-2"><Label>Address</Label>
          <Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })}
            data-testid="admin-agent-profile-address-input" /></div>
      </div>
      {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
      <div className="flex justify-end">
        <Button type="submit" disabled={busy} data-testid="admin-agent-profile-save">
          {busy ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </form>
  );
}

export default function AdminAgentDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data: agent, isLoading, isError } = useAgent(id);
  const [resetUrl, setResetUrl] = useState("");

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["admin-agent", id] });
    qc.invalidateQueries({ queryKey: ["admin-agent-txns", id] });
    qc.invalidateQueries({ queryKey: ["admin-agent-audit", id] });
    qc.invalidateQueries({ queryKey: ["admin-dashboard"] });
  };

  const toggleStatus = async () => {
    const next = agent.status === "active" ? "disabled" : "active";
    try {
      await api.patch(`/admin/agents/${agent.id}/status`, { status: next });
      toast.success(`Agent ${next}`);
      refresh();
    } catch (err) { toast.error(formatApiError(err)); }
  };
  const issueReset = async () => {
    try {
      const { data } = await api.post(`/admin/agents/${agent.id}/reset-password`, {});
      if (data.reset_path) setResetUrl(`${window.location.origin}${data.reset_path}`);
      toast.success("Reset link issued");
    } catch (err) { toast.error(formatApiError(err)); }
  };

  if (isLoading) {
    return <AdminShell title="Agent"><div className="h-64 rounded-lg bg-stone-100 animate-pulse" /></AdminShell>;
  }
  if (isError || !agent) {
    return (
      <AdminShell title="Agent">
        <div className="text-sm text-stone-600" data-testid="admin-agent-not-found">
          Agent not found. <Link className="underline" to="/admin/agents">Back to agents</Link>
        </div>
      </AdminShell>
    );
  }

  return (
    <AdminShell
      subtitle={<Link to="/admin/agents" className="inline-flex items-center gap-1 hover:underline"><ArrowLeft size={12}/>Agents</Link>}
      title={agent.display_name}
      actions={
        <div className="flex flex-wrap gap-2">
          <AdjustBalanceDialog agent={agent} onDone={refresh} />
          <Button variant="outline" onClick={issueReset} data-testid="admin-agent-reset-password">
            Reset password
          </Button>
          <Button
            variant={agent.status === "active" ? "destructive" : "default"}
            onClick={toggleStatus}
            data-testid="admin-agent-toggle-status"
          >
            {agent.status === "active" ? "Disable" : "Enable"}
          </Button>
        </div>
      }
    >
      <div className="space-y-6" data-testid="admin-agent-detail">
        {/* summary strip */}
        <div className="grid gap-4 sm:grid-cols-4">
          <Card>
            <CardHeader className="pb-2"><CardDescription>Email</CardDescription>
              <CardTitle className="text-base font-medium break-all">{agent.email}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardDescription>Status</CardDescription>
              <CardTitle><Badge className={STATUS_TONES[agent.status]}>{agent.status}</Badge></CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardDescription>Booking balance</CardDescription>
              <CardTitle className="text-2xl font-semibold" data-testid="admin-agent-booking-balance">
                {formatPHP(agent.booking_balance)}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardDescription>Commission balance</CardDescription>
              <CardTitle className="text-2xl font-semibold" data-testid="admin-agent-commission-balance">
                {formatPHP(agent.commission_balance)}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>

        {resetUrl ? (
          <Alert data-testid="admin-agent-reset-url-alert">
            <AlertDescription>
              <div className="mb-2">Share the reset link (expires in 4 hours):</div>
              <div className="flex items-center gap-2 rounded-md bg-stone-100 p-2">
                <div className="flex-1 font-mono text-xs break-all">{resetUrl}</div>
                <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(resetUrl); toast.success("Copied"); }}>
                  <Copy size={14} />
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        ) : null}

        {/* tabs */}
        <Tabs defaultValue="transactions" data-testid="admin-agent-tabs">
          <TabsList>
            <TabsTrigger value="transactions" data-testid="admin-agent-tab-transactions">Transactions</TabsTrigger>
            <TabsTrigger value="audit" data-testid="admin-agent-tab-audit">Audit trail</TabsTrigger>
            <TabsTrigger value="profile" data-testid="admin-agent-tab-profile">Profile</TabsTrigger>
          </TabsList>
          <TabsContent value="transactions" className="mt-4">
            <TransactionsPanel agentId={agent.id} />
          </TabsContent>
          <TabsContent value="audit" className="mt-4">
            <AuditPanel agentId={agent.id} />
          </TabsContent>
          <TabsContent value="profile" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle>Profile details</CardTitle>
                <CardDescription>Update contact information for this agent.</CardDescription>
              </CardHeader>
              <CardContent>
                <ProfileForm agent={agent} onSaved={refresh} />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AdminShell>
  );
}
