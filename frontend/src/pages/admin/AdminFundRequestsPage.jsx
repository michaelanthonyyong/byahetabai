import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api, formatApiError } from "@/lib/api";
import { formatPHP, timeAgo } from "@/lib/admin";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { CheckCircle2, XCircle, Plus, Loader2 } from "lucide-react";
import { toast } from "sonner";

const STATUS_TONES = {
  pending: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-700",
};

const TABS = ["", "pending", "approved", "rejected"];

export default function AdminFundRequestsPage() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const status = params.get("status") || "";

  const filters = useMemo(
    () => ({ status: status || undefined }),
    [status],
  );

  const { data, isLoading } = useQuery({
    queryKey: ["admin-fund-requests", filters],
    queryFn: () => api.get("/admin/fund-requests", { params: filters }).then((r) => r.data),
  });

  const setTab = (s) => {
    const next = new URLSearchParams(params);
    if (s) next.set("status", s); else next.delete("status");
    setParams(next, { replace: true });
  };

  const [decideTarget, setDecideTarget] = useState(null); // { row, kind: 'approve'|'reject' }
  const [createOpen, setCreateOpen] = useState(false);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin-fund-requests"] });
    qc.invalidateQueries({ queryKey: ["admin-dashboard"] });
    qc.invalidateQueries({ queryKey: ["admin-agent"] });
  };

  return (
    <AdminShell
      subtitle="Approvals"
      title="Fund Requests"
      actions={
        <Button onClick={() => setCreateOpen(true)} data-testid="admin-fund-request-new-button">
          <Plus size={16} className="mr-1.5" />New request
        </Button>
      }
    >
      <div className="space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="inline-flex rounded-lg border border-stone-200 bg-white p-1" data-testid="admin-fund-requests-tabs">
            {TABS.map((s) => (
              <button
                key={s}
                onClick={() => setTab(s)}
                data-testid={`admin-fund-requests-filter-${s || "all"}`}
                className={[
                  "px-3 py-1.5 text-sm rounded-md capitalize",
                  status === s ? "bg-stone-900 text-white" : "text-stone-600 hover:text-stone-900",
                ].join(" ")}
              >
                {s || "all"}
              </button>
            ))}
          </div>
          <div className="text-xs text-stone-500">
            <span data-testid="admin-fund-requests-pending-count">{data?.pending_count ?? 0}</span> pending
          </div>
        </div>

        {isLoading ? (
          <div className="h-64 rounded-lg bg-stone-100 animate-pulse" />
        ) : !data?.fund_requests?.length ? (
          <div
            className="rounded-lg border border-dashed border-stone-200 p-10 text-center text-sm text-stone-500"
            data-testid="admin-fund-requests-empty"
          >
            No fund requests match those filters.
          </div>
        ) : (
          <>
            <div className="text-xs text-stone-500">
              {data.total} total · showing {data.fund_requests.length}
            </div>
            <Card>
              <CardContent className="p-0 overflow-x-auto">
                <table className="w-full text-sm min-w-[900px]" data-testid="admin-fund-requests-table">
                  <thead className="border-b border-stone-200 bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                    <tr>
                      <th className="px-4 py-3 text-left">Agent</th>
                      <th className="px-4 py-3 text-right">Amount</th>
                      <th className="px-4 py-3 text-left">Reference</th>
                      <th className="px-4 py-3 text-left">Note</th>
                      <th className="px-4 py-3 text-left">Submitted</th>
                      <th className="px-4 py-3 text-left">Status</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.fund_requests.map((fr) => (
                      <tr
                        key={fr.id}
                        className="border-t border-stone-100 hover:bg-stone-50"
                        data-testid={`admin-fund-request-row-${fr.id}`}
                      >
                        <td className="px-4 py-3">
                          <div className="text-stone-900">{fr.agent?.display_name || "—"}</div>
                          <div className="text-xs text-stone-500">{fr.agent?.agency_name || ""}</div>
                        </td>
                        <td className="px-4 py-3 text-right font-mono">{formatPHP(fr.amount)}</td>
                        <td className="px-4 py-3 font-mono text-xs text-stone-700">
                          {fr.reference_no || <span className="text-stone-400">—</span>}
                        </td>
                        <td className="px-4 py-3 text-xs text-stone-600 max-w-[260px] truncate" title={fr.note || ""}>
                          {fr.note || <span className="text-stone-400">—</span>}
                        </td>
                        <td className="px-4 py-3 text-xs text-stone-500">{timeAgo(fr.created_at)}</td>
                        <td className="px-4 py-3">
                          <Badge className={STATUS_TONES[fr.status]}>{fr.status}</Badge>
                        </td>
                        <td className="px-4 py-3 text-right">
                          {fr.status === "pending" ? (
                            <div className="flex justify-end gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setDecideTarget({ row: fr, kind: "reject" })}
                                data-testid={`admin-fund-request-reject-${fr.id}`}
                              >
                                <XCircle size={12} className="mr-1" />Reject
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => setDecideTarget({ row: fr, kind: "approve" })}
                                data-testid={`admin-fund-request-approve-${fr.id}`}
                              >
                                <CheckCircle2 size={12} className="mr-1" />Approve
                              </Button>
                            </div>
                          ) : (
                            <div className="text-xs text-stone-500">
                              {fr.decided_at ? timeAgo(fr.decided_at) : "—"}
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
            <Alert>
              <AlertDescription className="text-xs">
                Approving a request credits the agent's booking balance atomically via a TOP_UP ledger row.
                Re-clicking approve is safe (idempotent). Rejection requires a reason.
              </AlertDescription>
            </Alert>
          </>
        )}
      </div>

      {decideTarget ? (
        <DecideDialog
          target={decideTarget}
          onClose={() => setDecideTarget(null)}
          onDone={invalidate}
        />
      ) : null}
      {createOpen ? (
        <CreateDialog
          onClose={() => setCreateOpen(false)}
          onDone={invalidate}
        />
      ) : null}
    </AdminShell>
  );
}

/* ------------------------------------------------------------------ */
/* Approve / Reject dialog                                            */
/* ------------------------------------------------------------------ */
function DecideDialog({ target, onClose, onDone }) {
  const { row, kind } = target;
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (kind === "reject" && note.trim().length < 3) {
      toast.error("Rejection reason must be at least 3 characters.");
      return;
    }
    setBusy(true);
    try {
      const path = `/admin/fund-requests/${row.id}/${kind}`;
      const body = kind === "approve"
        ? { decision_note: note.trim() || null }
        : { decision_note: note.trim() };
      const { data } = await api.post(path, body);
      if (kind === "approve") {
        if (data.already_approved) {
          toast.info("Already approved.");
        } else {
          toast.success(`Approved — new booking balance ₱${Number(data.booking_balance).toLocaleString()}`);
        }
      } else {
        toast.success("Request rejected.");
      }
      onDone();
      onClose();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent data-testid={`admin-fund-request-${kind}-dialog`}>
        <DialogHeader>
          <DialogTitle>
            {kind === "approve" ? "Approve fund request" : "Reject fund request"}
          </DialogTitle>
          <DialogDescription>
            {kind === "approve"
              ? `Credit ₱${Number(row.amount).toLocaleString()} to ${row.agent?.display_name}'s booking account. This is atomic and idempotent.`
              : `Mark this request as rejected. No money is moved; a reason is required.`}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="rounded-md border border-stone-200 bg-stone-50 p-3 text-sm">
            <div className="flex justify-between">
              <span className="text-stone-500">Agent</span>
              <span className="text-stone-900">{row.agent?.display_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-stone-500">Amount</span>
              <span className="font-mono text-stone-900">{formatPHP(row.amount)}</span>
            </div>
            {row.reference_no ? (
              <div className="flex justify-between">
                <span className="text-stone-500">Reference</span>
                <span className="font-mono text-xs text-stone-700">{row.reference_no}</span>
              </div>
            ) : null}
          </div>
          <div>
            <Label htmlFor="decision-note">
              {kind === "approve" ? "Note (optional)" : "Reason (required)"}
            </Label>
            <Textarea
              id="decision-note"
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={400}
              placeholder={kind === "approve" ? "e.g. deposit verified with bank" : "e.g. reference number does not match any deposit"}
              data-testid={`admin-fund-request-${kind}-note`}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button
            onClick={submit}
            disabled={busy}
            variant={kind === "reject" ? "destructive" : "default"}
            data-testid={`admin-fund-request-${kind}-confirm`}
          >
            {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}
            {kind === "approve" ? "Approve & credit" : "Reject"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ */
/* Create-on-behalf dialog                                            */
/* ------------------------------------------------------------------ */
function CreateDialog({ onClose, onDone }) {
  const [agentId, setAgentId] = useState("");
  const [amount, setAmount] = useState("");
  const [ref, setRef] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const { data: agentsData, isLoading: agentsLoading } = useQuery({
    queryKey: ["admin-agents", "for-fund-request"],
    queryFn: () => api.get("/admin/agents", { params: { page_size: 100, status: "active" } }).then((r) => r.data),
  });
  const agents = agentsData?.agents || [];

  const submit = async () => {
    const amt = Number(amount);
    if (!agentId) return toast.error("Pick an agent.");
    if (!Number.isFinite(amt) || amt < 100 || amt > 1000000) {
      return toast.error("Amount must be between ₱100 and ₱1,000,000.");
    }
    setBusy(true);
    try {
      await api.post("/admin/fund-requests", {
        agent_id: agentId,
        amount: amount,
        reference_no: ref.trim() || null,
        note: note.trim() || null,
      });
      toast.success("Fund request created — pending approval.");
      onDone();
      onClose();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent data-testid="admin-fund-request-create-dialog">
        <DialogHeader>
          <DialogTitle>New fund request</DialogTitle>
          <DialogDescription>
            File a top-up request on behalf of an agent. It lands as <b>pending</b> so the
            approval flow still applies.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>Agent</Label>
            <Select value={agentId} onValueChange={setAgentId} disabled={agentsLoading}>
              <SelectTrigger data-testid="admin-fund-request-create-agent">
                <SelectValue placeholder={agentsLoading ? "Loading…" : "Select an active agent"} />
              </SelectTrigger>
              <SelectContent>
                {agents.map((a) => (
                  <SelectItem key={a.id} value={a.id} data-testid={`admin-fund-request-agent-${a.id}`}>
                    {a.display_name}{a.agency_name ? ` · ${a.agency_name}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="amount">Amount (PHP)</Label>
            <Input
              id="amount" type="number" min="100" max="1000000" step="0.01"
              value={amount} onChange={(e) => setAmount(e.target.value)}
              placeholder="e.g. 5000.00"
              data-testid="admin-fund-request-create-amount"
            />
            <p className="text-[11px] text-stone-500 mt-1">Min ₱100 · Max ₱1,000,000</p>
          </div>
          <div>
            <Label htmlFor="ref">Reference number</Label>
            <Input
              id="ref" value={ref} onChange={(e) => setRef(e.target.value)} maxLength={120}
              placeholder="Deposit slip / bank ref"
              data-testid="admin-fund-request-create-ref"
            />
          </div>
          <div>
            <Label htmlFor="cnote">Note</Label>
            <Textarea
              id="cnote" rows={2} value={note} onChange={(e) => setNote(e.target.value)} maxLength={400}
              data-testid="admin-fund-request-create-note"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button onClick={submit} disabled={busy} data-testid="admin-fund-request-create-confirm">
            {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}
            Create pending request
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
