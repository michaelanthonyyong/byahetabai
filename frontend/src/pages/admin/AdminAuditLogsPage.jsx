import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api } from "@/lib/api";
import { humanAction, timeAgo } from "@/lib/admin";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";

const SENTINEL_ALL = "__all__";

export default function AdminAuditLogsPage() {
  const [params, setParams] = useSearchParams();
  const [openId, setOpenId] = useState(null);

  const filters = useMemo(() => ({
    action: params.get("action") || undefined,
    target_type: params.get("target_type") || undefined,
    target_id: params.get("target_id") || undefined,
    actor_user_id: params.get("actor_user_id") || undefined,
    date_from: params.get("date_from") || undefined,
    date_to: params.get("date_to") || undefined,
    page_size: 50,
  }), [params]);

  const setParam = (k, v) => {
    const next = new URLSearchParams(params);
    if (v && v !== SENTINEL_ALL) next.set(k, v); else next.delete(k);
    setParams(next, { replace: true });
  };

  const { data: meta } = useQuery({
    queryKey: ["admin-audit-actions"],
    queryFn: () => api.get("/admin/audit-logs/actions").then((r) => r.data),
  });
  const { data, isLoading } = useQuery({
    queryKey: ["admin-audit-logs", filters],
    queryFn: () => api.get("/admin/audit-logs", { params: filters }).then((r) => r.data),
  });

  return (
    <AdminShell subtitle="Security" title="Audit Log">
      <div className="space-y-6">
        <Card>
          <CardContent className="p-4 grid gap-3 md:grid-cols-5">
            <div>
              <Label className="text-xs">Action</Label>
              <Select
                value={params.get("action") || SENTINEL_ALL}
                onValueChange={(v) => setParam("action", v)}
              >
                <SelectTrigger data-testid="audit-filter-action"><SelectValue placeholder="Any" /></SelectTrigger>
                <SelectContent className="max-h-72">
                  <SelectItem value={SENTINEL_ALL}>Any action</SelectItem>
                  {(meta?.actions || []).map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Entity</Label>
              <Select
                value={params.get("target_type") || SENTINEL_ALL}
                onValueChange={(v) => setParam("target_type", v)}
              >
                <SelectTrigger data-testid="audit-filter-target"><SelectValue placeholder="Any" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={SENTINEL_ALL}>Any entity</SelectItem>
                  {(meta?.target_types || []).map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Target ID</Label>
              <Input
                value={params.get("target_id") || ""}
                onChange={(e) => setParam("target_id", e.target.value)}
                placeholder="UUID"
                data-testid="audit-filter-target-id"
              />
            </div>
            <div>
              <Label className="text-xs">From</Label>
              <Input type="date" value={params.get("date_from") || ""} onChange={(e) => setParam("date_from", e.target.value)} />
            </div>
            <div>
              <Label className="text-xs">To</Label>
              <Input type="date" value={params.get("date_to") || ""} onChange={(e) => setParam("date_to", e.target.value)} />
            </div>
          </CardContent>
        </Card>

        {isLoading ? (
          <div className="h-64 rounded-lg bg-stone-100 animate-pulse" />
        ) : !data?.audit_logs?.length ? (
          <div className="rounded-lg border border-dashed border-stone-200 p-10 text-center text-sm text-stone-500" data-testid="admin-audit-empty">
            No audit entries match those filters.
          </div>
        ) : (
          <>
            <div className="text-xs text-stone-500">{data.total} total · showing {data.audit_logs.length}</div>
            <Card>
              <CardContent className="p-0 overflow-x-auto">
                <table className="w-full text-sm min-w-[900px]" data-testid="admin-audit-table">
                  <thead className="border-b border-stone-200 bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                    <tr>
                      <th className="px-4 py-3 text-left">When</th>
                      <th className="px-4 py-3 text-left">Actor</th>
                      <th className="px-4 py-3 text-left">Action</th>
                      <th className="px-4 py-3 text-left">Target</th>
                      <th className="px-4 py-3 text-right">Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.audit_logs.map((r) => (
                      <tr key={r.id} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`admin-audit-row-${r.id}`}>
                        <td className="px-4 py-3 text-xs text-stone-500 whitespace-nowrap">{timeAgo(r.created_at)}</td>
                        <td className="px-4 py-3">
                          <div className="text-stone-900">{r.actor?.display_name || r.actor?.email || r.actor_user_id || "system"}</div>
                          <div className="text-xs text-stone-500 uppercase tracking-widest">{r.actor_role || ""}</div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-stone-800">{humanAction(r.action)}</div>
                          <div className="text-[10px] text-stone-400 font-mono">{r.action}</div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant="outline" className="capitalize">{r.target_type}</Badge>
                          <div className="text-[10px] text-stone-400 font-mono">{(r.target_id || "").slice(0, 8)}</div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button size="sm" variant="outline" onClick={() => setOpenId(r.id)} data-testid={`admin-audit-open-${r.id}`}>
                            View
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {openId ? (
        <DetailPanel
          row={data?.audit_logs?.find((r) => r.id === openId)}
          onClose={() => setOpenId(null)}
        />
      ) : null}
    </AdminShell>
  );
}

function DetailPanel({ row, onClose }) {
  if (!row) return null;
  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex items-start justify-end"
      onClick={onClose}
      data-testid="admin-audit-detail"
    >
      <div className="w-full sm:w-[540px] h-full bg-white overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.25em] text-stone-500">Audit entry</div>
            <div className="text-stone-900 font-semibold">{humanAction(row.action)}</div>
            <div className="text-xs text-stone-500 font-mono">{row.action}</div>
          </div>
          <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
        </div>
        <dl className="text-sm space-y-3">
          <Row label="When">{new Date(row.created_at).toLocaleString()}</Row>
          <Row label="Actor">{row.actor?.display_name || row.actor?.email || row.actor_user_id} · {row.actor_role}</Row>
          <Row label="Target">{row.target_type} · <span className="font-mono text-xs">{row.target_id}</span></Row>
          {row.ip ? <Row label="IP">{row.ip}</Row> : null}
          {row.user_agent ? <Row label="User agent" mono>{row.user_agent}</Row> : null}
          {row.note ? <Row label="Note">{row.note}</Row> : null}
          {row.before ? <Row label="Before"><pre className="text-xs bg-stone-50 p-2 rounded overflow-x-auto">{JSON.stringify(row.before, null, 2)}</pre></Row> : null}
          {row.after ? <Row label="After"><pre className="text-xs bg-stone-50 p-2 rounded overflow-x-auto">{JSON.stringify(row.after, null, 2)}</pre></Row> : null}
        </dl>
      </div>
    </div>
  );
}

function Row({ label, children, mono }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-widest text-stone-500">{label}</dt>
      <dd className={"text-stone-800 " + (mono ? "font-mono text-xs break-all" : "")}>{children}</dd>
    </div>
  );
}
