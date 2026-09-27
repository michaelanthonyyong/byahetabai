import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api } from "@/lib/api";
import { formatPHP, timeAgo } from "@/lib/admin";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Download } from "lucide-react";

const TYPES = [
  "TOP_UP", "BOOKING_DEBIT", "BOOKING_REFUND",
  "COMMISSION_ACCRUAL", "COMMISSION_REVERSAL", "COMMISSION_WITHDRAWAL",
  "ADJUSTMENT_CREDIT", "ADJUSTMENT_DEBIT",
];

const TYPE_TONES = {
  TOP_UP: "bg-emerald-100 text-emerald-800",
  BOOKING_REFUND: "bg-emerald-100 text-emerald-800",
  COMMISSION_ACCRUAL: "bg-emerald-100 text-emerald-800",
  ADJUSTMENT_CREDIT: "bg-emerald-100 text-emerald-800",
  BOOKING_DEBIT: "bg-red-100 text-red-700",
  COMMISSION_WITHDRAWAL: "bg-red-100 text-red-700",
  COMMISSION_REVERSAL: "bg-red-100 text-red-700",
  ADJUSTMENT_DEBIT: "bg-red-100 text-red-700",
};

const SENTINEL_ALL = "__all__";

export default function AdminTransactionsPage() {
  const [params, setParams] = useSearchParams();

  const filters = useMemo(() => ({
    agent_id: params.get("agent_id") || undefined,
    account_kind: params.get("account_kind") || undefined,
    type: params.get("type") || undefined,
    date_from: params.get("date_from") || undefined,
    date_to: params.get("date_to") || undefined,
    page_size: 50,
  }), [params]);

  const setParam = (k, v) => {
    const next = new URLSearchParams(params);
    if (v && v !== SENTINEL_ALL) next.set(k, v); else next.delete(k);
    setParams(next, { replace: true });
  };

  const { data: agentsData } = useQuery({
    queryKey: ["admin-agents", "for-transactions"],
    queryFn: () => api.get("/admin/agents", { params: { page_size: 100 } }).then((r) => r.data),
  });
  const agents = agentsData?.agents || [];

  const { data, isLoading } = useQuery({
    queryKey: ["admin-transactions", filters],
    queryFn: () => api.get("/admin/transactions", { params: filters }).then((r) => r.data),
  });

  const downloadCsv = async () => {
    const qs = new URLSearchParams(
      Object.entries({ ...filters, page_size: undefined, limit: 5000 })
        .filter(([, v]) => v != null && v !== "")
    ).toString();
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/admin/transactions/export.csv${qs ? `?${qs}` : ""}`;
    // Trigger browser download while keeping the cookie session.
    window.open(url, "_blank");
  };

  return (
    <AdminShell
      subtitle="Finance"
      title="Transactions"
      actions={
        <Button onClick={downloadCsv} variant="outline" data-testid="admin-transactions-export">
          <Download size={14} className="mr-1.5" />Download CSV
        </Button>
      }
    >
      <div className="space-y-6">
        <Card>
          <CardContent className="p-4 grid gap-3 md:grid-cols-5">
            <div>
              <Label className="text-xs">Agent</Label>
              <Select
                value={params.get("agent_id") || SENTINEL_ALL}
                onValueChange={(v) => setParam("agent_id", v)}
              >
                <SelectTrigger data-testid="tx-filter-agent"><SelectValue placeholder="All agents" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={SENTINEL_ALL}>All agents</SelectItem>
                  {agents.map((a) => (
                    <SelectItem key={a.id} value={a.id}>{a.display_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Account</Label>
              <Select
                value={params.get("account_kind") || SENTINEL_ALL}
                onValueChange={(v) => setParam("account_kind", v)}
              >
                <SelectTrigger data-testid="tx-filter-account"><SelectValue placeholder="All accounts" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={SENTINEL_ALL}>All accounts</SelectItem>
                  <SelectItem value="booking">Booking</SelectItem>
                  <SelectItem value="commission">Commission</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Type</Label>
              <Select
                value={params.get("type") || SENTINEL_ALL}
                onValueChange={(v) => setParam("type", v)}
              >
                <SelectTrigger data-testid="tx-filter-type"><SelectValue placeholder="All types" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={SENTINEL_ALL}>All types</SelectItem>
                  {TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">From</Label>
              <Input
                type="date"
                value={params.get("date_from") || ""}
                onChange={(e) => setParam("date_from", e.target.value)}
                data-testid="tx-filter-from"
              />
            </div>
            <div>
              <Label className="text-xs">To</Label>
              <Input
                type="date"
                value={params.get("date_to") || ""}
                onChange={(e) => setParam("date_to", e.target.value)}
                data-testid="tx-filter-to"
              />
            </div>
          </CardContent>
        </Card>

        {isLoading ? (
          <div className="h-64 rounded-lg bg-stone-100 animate-pulse" />
        ) : !data?.transactions?.length ? (
          <div className="rounded-lg border border-dashed border-stone-200 p-10 text-center text-sm text-stone-500" data-testid="admin-transactions-empty">
            No transactions match those filters.
          </div>
        ) : (
          <>
            <div className="text-xs text-stone-500">{data.total} total · showing {data.transactions.length}</div>
            <Card>
              <CardContent className="p-0 overflow-x-auto">
                <table className="w-full text-sm min-w-[900px]" data-testid="admin-transactions-table">
                  <thead className="border-b border-stone-200 bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                    <tr>
                      <th className="px-4 py-3 text-left">When</th>
                      <th className="px-4 py-3 text-left">Agent</th>
                      <th className="px-4 py-3 text-left">Account</th>
                      <th className="px-4 py-3 text-left">Type</th>
                      <th className="px-4 py-3 text-right">Amount</th>
                      <th className="px-4 py-3 text-right">Balance after</th>
                      <th className="px-4 py-3 text-left">Ref</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.transactions.map((t) => (
                      <tr key={t.id} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`admin-tx-row-${t.id}`}>
                        <td className="px-4 py-3 text-xs text-stone-500 whitespace-nowrap">{timeAgo(t.created_at)}</td>
                        <td className="px-4 py-3">{t.agent?.display_name || t.agent_id}</td>
                        <td className="px-4 py-3"><Badge variant="outline" className="capitalize">{t.account_kind}</Badge></td>
                        <td className="px-4 py-3"><Badge className={TYPE_TONES[t.type] || "bg-stone-100 text-stone-700"}>{t.type}</Badge></td>
                        <td className={"px-4 py-3 text-right font-mono " + (t.amount.startsWith("-") ? "text-red-600" : "text-emerald-700")}>
                          {formatPHP(t.amount)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-stone-700">{formatPHP(t.balance_after)}</td>
                        <td className="px-4 py-3 text-xs text-stone-500 font-mono">
                          {t.ref_type ? <>{t.ref_type} · <span className="text-stone-400">{(t.ref_id || "").slice(0, 8)}</span></> : "—"}
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
    </AdminShell>
  );
}
