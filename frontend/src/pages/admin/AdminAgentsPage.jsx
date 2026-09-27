import { useEffect, useState } from "react";
import PortalHeader from "@/components/portal/PortalHeader";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function LinkBox({ url, testid }) {
  return (
    <div className="rounded-md bg-stone-100 px-3 py-2 text-xs break-all font-mono" data-testid={testid}>
      {url}
    </div>
  );
}

function InviteDialog({ onCreated }) {
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
      const full = `${window.location.origin}${data.invite_path}`;
      setInviteUrl(full);
      onCreated?.();
      toast.success("Agent invited");
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setForm({ email: "", display_name: "", agency_name: "", phone: "" });
    setInviteUrl("");
    setError("");
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) reset(); }}>
      <DialogTrigger asChild>
        <Button data-testid="admin-invite-agent-button">Invite agent</Button>
      </DialogTrigger>
      <DialogContent data-testid="admin-invite-agent-dialog">
        <DialogHeader>
          <DialogTitle>Invite a new agent</DialogTitle>
          <DialogDescription>
            The agent will receive a URL below; they set their own password on first use.
          </DialogDescription>
        </DialogHeader>
        {inviteUrl ? (
          <div className="space-y-3">
            <Alert>
              <AlertDescription>
                Share this one-time invitation link with the agent. It expires in 72 hours.
              </AlertDescription>
            </Alert>
            <LinkBox url={inviteUrl} testid="admin-invite-url" />
            <DialogFooter>
              <Button
                onClick={() => {
                  navigator.clipboard.writeText(inviteUrl);
                  toast.success("Copied");
                }}
                data-testid="admin-invite-copy-button"
              >
                Copy link
              </Button>
              <Button variant="outline" onClick={() => setOpen(false)}>Close</Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="i-email">Email</Label>
              <Input
                id="i-email" type="email" required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                data-testid="admin-invite-email-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="i-name">Display name</Label>
              <Input
                id="i-name" required
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                data-testid="admin-invite-name-input"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="i-agency">Agency (optional)</Label>
                <Input
                  id="i-agency"
                  value={form.agency_name}
                  onChange={(e) => setForm({ ...form, agency_name: e.target.value })}
                  data-testid="admin-invite-agency-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="i-phone">Phone (optional)</Label>
                <Input
                  id="i-phone"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  data-testid="admin-invite-phone-input"
                />
              </div>
            </div>
            {error ? (
              <Alert variant="destructive" data-testid="admin-invite-error">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
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

function AgentRow({ a, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [resetUrl, setResetUrl] = useState("");

  const doReset = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/admin/agents/${a.id}/reset-password`, {});
      if (data.reset_path) setResetUrl(`${window.location.origin}${data.reset_path}`);
      toast.success("Reset link issued");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const toggleStatus = async () => {
    const next = a.status === "active" ? "disabled" : "active";
    setBusy(true);
    try {
      await api.patch(`/admin/agents/${a.id}/status`, { status: next });
      toast.success(`Agent ${next}`);
      onChanged?.();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const statusColor =
    a.status === "active" ? "bg-emerald-100 text-emerald-800" :
    a.status === "invited" ? "bg-amber-100 text-amber-800" :
    "bg-stone-200 text-stone-700";

  return (
    <div
      className="grid grid-cols-12 items-center gap-3 border-t border-stone-100 px-4 py-3 text-sm"
      data-testid={`admin-agent-row-${a.id}`}
    >
      <div className="col-span-4">
        <div className="font-medium text-stone-900">{a.display_name}</div>
        <div className="text-xs text-stone-500">{a.email}</div>
      </div>
      <div className="col-span-3 text-stone-600">{a.agency_name || "—"}</div>
      <div className="col-span-2">
        <Badge className={statusColor}>{a.status}</Badge>
      </div>
      <div className="col-span-3 flex flex-wrap justify-end gap-2">
        <Button size="sm" variant="outline" disabled={busy} onClick={doReset}
          data-testid={`admin-agent-reset-${a.id}`}>
          Reset password
        </Button>
        <Button size="sm" variant={a.status === "active" ? "destructive" : "default"} disabled={busy}
          onClick={toggleStatus}
          data-testid={`admin-agent-toggle-${a.id}`}>
          {a.status === "active" ? "Disable" : "Enable"}
        </Button>
      </div>
      {resetUrl ? (
        <div className="col-span-12 space-y-2">
          <Alert>
            <AlertDescription>Share this reset link with the agent (expires in 4 hours):</AlertDescription>
          </Alert>
          <LinkBox url={resetUrl} testid={`admin-agent-reset-url-${a.id}`} />
        </div>
      ) : null}
    </div>
  );
}

export default function AdminAgentsPage() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/agents");
      setAgents(data.agents);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="min-h-screen bg-stone-50">
      <PortalHeader title="Admin · Agents" />
      <main className="mx-auto max-w-6xl px-6 py-10 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-stone-900">Agents</h1>
            <p className="text-sm text-stone-600 mt-1">Invite, disable and reset passwords.</p>
          </div>
          <InviteDialog onCreated={load} />
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All agents</CardTitle>
            <CardDescription>{agents.length} total</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="grid grid-cols-12 gap-3 border-b border-stone-200 bg-stone-50 px-4 py-2 text-xs uppercase tracking-wider text-stone-500">
              <div className="col-span-4">Agent</div>
              <div className="col-span-3">Agency</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-3 text-right">Actions</div>
            </div>
            {loading ? (
              <div className="p-6 text-sm text-stone-500" data-testid="admin-agents-loading">Loading…</div>
            ) : error ? (
              <div className="p-6"><Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert></div>
            ) : agents.length === 0 ? (
              <div className="p-6 text-sm text-stone-500">No agents yet. Invite your first agent.</div>
            ) : (
              agents.map((a) => <AgentRow key={a.id} a={a} onChanged={load} />)
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
