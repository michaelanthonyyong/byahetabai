import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api, formatApiError } from "@/lib/api";
import { formatPHP, timeAgo } from "@/lib/admin";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Search, UserPlus, ExternalLink, Copy } from "lucide-react";
import { toast } from "sonner";

const STATUS_TONES = {
  active: "bg-emerald-100 text-emerald-800",
  invited: "bg-amber-100 text-amber-800",
  disabled: "bg-stone-200 text-stone-700",
};

function StatusBadge({ status }) {
  return <Badge className={STATUS_TONES[status] || "bg-stone-200"}>{status}</Badge>;
}

function CopyLink({ url, testid }) {
  return (
    <div className="flex items-center gap-2 rounded-md bg-stone-100 p-2">
      <div className="flex-1 font-mono text-xs break-all" data-testid={testid}>{url}</div>
      <Button
        size="sm" variant="outline"
        onClick={() => { navigator.clipboard.writeText(url); toast.success("Copied"); }}
        data-testid={`${testid}-copy`}
      >
        <Copy size={14} />
      </Button>
    </div>
  );
}

function InviteAgentDialog() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", display_name: "", agency_name: "", phone: "" });
  const [inviteUrl, setInviteUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post("/admin/agents", form);
      setInviteUrl(`${window.location.origin}${data.invite_path}`);
      qc.invalidateQueries({ queryKey: ["admin-agents"] });
      qc.invalidateQueries({ queryKey: ["admin-dashboard"] });
      toast.success("Agent invited");
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setForm({ email: "", display_name: "", agency_name: "", phone: "" });
    setInviteUrl(""); setError(""); setBusy(false);
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) reset(); }}>
      <DialogTrigger asChild>
        <Button data-testid="admin-invite-agent-button">
          <UserPlus size={16} className="mr-1.5" />Invite agent
        </Button>
      </DialogTrigger>
      <DialogContent data-testid="admin-invite-agent-dialog">
        <DialogHeader>
          <DialogTitle>Invite a new agent</DialogTitle>
          <DialogDescription>Share the URL below with the agent — they set their password on first use. Expires in 72 hours.</DialogDescription>
        </DialogHeader>
        {inviteUrl ? (
          <div className="space-y-3">
            <Alert><AlertDescription>Invitation ready.</AlertDescription></Alert>
            <CopyLink url={inviteUrl} testid="admin-invite-url" />
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>Close</Button>
            </DialogFooter>
          </div>
        ) : (
          <form className="space-y-4" onSubmit={submit}>
            <div className="space-y-2"><Label htmlFor="i-email">Email</Label>
              <Input id="i-email" type="email" required value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                data-testid="admin-invite-email-input" /></div>
            <div className="space-y-2"><Label htmlFor="i-name">Display name</Label>
              <Input id="i-name" required value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                data-testid="admin-invite-name-input" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2"><Label htmlFor="i-agency">Agency</Label>
                <Input id="i-agency" value={form.agency_name}
                  onChange={(e) => setForm({ ...form, agency_name: e.target.value })}
                  data-testid="admin-invite-agency-input" /></div>
              <div className="space-y-2"><Label htmlFor="i-phone">Phone</Label>
                <Input id="i-phone" value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  data-testid="admin-invite-phone-input" /></div>
            </div>
            {error ? <Alert variant="destructive" data-testid="admin-invite-error"><AlertDescription>{error}</AlertDescription></Alert> : null}
            <DialogFooter>
              <Button type="submit" disabled={busy} data-testid="admin-invite-submit-button">
                {busy ? "Inviting…" : "Send invitation"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

function AgentsTable({ agents }) {
  if (!agents.length) {
    return (
      <div className="rounded-lg border border-dashed border-stone-200 p-10 text-center text-sm text-stone-500" data-testid="admin-agents-empty">
        No agents match those filters.
      </div>
    );
  }
  return (
    <Card>
      <CardContent className="p-0 overflow-x-auto">
        <table className="w-full text-sm min-w-[720px]" data-testid="admin-agents-table">
          <thead className="border-b border-stone-200 bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
            <tr>
              <th className="px-4 py-3 text-left">Agent</th>
              <th className="px-4 py-3 text-left">Agency</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-right">Booking balance</th>
              <th className="px-4 py-3 text-right">Commission</th>
              <th className="px-4 py-3 text-right">Last login</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => (
              <tr key={a.id} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`admin-agent-row-${a.id}`}>
                <td className="px-4 py-3">
                  <div className="font-medium text-stone-900">{a.display_name}</div>
                  <div className="text-xs text-stone-500">{a.email}</div>
                </td>
                <td className="px-4 py-3 text-stone-600">{a.agency_name || "—"}</td>
                <td className="px-4 py-3"><StatusBadge status={a.status} /></td>
                <td className="px-4 py-3 text-right font-mono">{formatPHP(a.booking_balance)}</td>
                <td className="px-4 py-3 text-right font-mono">{formatPHP(a.commission_balance)}</td>
                <td className="px-4 py-3 text-right text-xs text-stone-500">
                  {a.last_login_at ? timeAgo(a.last_login_at) : "—"}
                </td>
                <td className="px-4 py-3 text-right">
                  <Button asChild size="sm" variant="outline" data-testid={`admin-agent-open-${a.id}`}>
                    <Link to={`/admin/agents/${a.id}`}>Open<ExternalLink size={12} className="ml-1" /></Link>
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

export default function AdminAgentsPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") || "";
  const [q, setQ] = useState(params.get("q") || "");
  const filters = useMemo(() => ({ status: status || undefined, q: params.get("q") || undefined }), [status, params]);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-agents", filters],
    queryFn: () => api.get("/admin/agents", { params: filters }).then((r) => r.data),
  });

  const setParam = (k, v) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    setParams(next, { replace: true });
  };

  useEffect(() => { setQ(params.get("q") || ""); }, [params]);

  const filtersActive = ["", "active", "invited", "disabled"];

  return (
    <AdminShell
      subtitle="People"
      title="Agents"
      actions={<InviteAgentDialog />}
    >
      <div className="space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="inline-flex rounded-lg border border-stone-200 bg-white p-1" data-testid="admin-agents-status-tabs">
            {filtersActive.map((s) => (
              <button
                key={s}
                onClick={() => setParam("status", s)}
                data-testid={`admin-agents-filter-${s || "all"}`}
                className={[
                  "px-3 py-1.5 text-sm rounded-md capitalize transition-colors",
                  status === s ? "bg-stone-900 text-white" : "text-stone-600 hover:text-stone-900",
                ].join(" ")}
              >
                {s || "all"}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 py-1.5 min-w-0 sm:min-w-[280px]">
            <Search size={14} className="text-stone-400 shrink-0" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && setParam("q", q.trim())}
              placeholder="Search email, name, or agency"
              className="w-full bg-transparent outline-none text-sm"
              data-testid="admin-agents-search-input"
            />
          </label>
        </div>

        {isLoading ? (
          <div className="h-64 rounded-lg bg-stone-100 animate-pulse" data-testid="admin-agents-loading" />
        ) : (
          <>
            <div className="text-xs text-stone-500">
              {data?.total || 0} agent{data?.total === 1 ? "" : "s"} · showing {data?.agents?.length || 0}
            </div>
            <AgentsTable agents={data?.agents || []} />
          </>
        )}
      </div>
    </AdminShell>
  );
}
