import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api } from "@/lib/api";
import { formatPHP, timeAgo } from "@/lib/admin";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Search, ExternalLink } from "lucide-react";

const STATUS_TONES = {
  pending: "bg-amber-100 text-amber-800",
  confirmed: "bg-sky-100 text-sky-800",
  cancelled: "bg-stone-200 text-stone-700",
  completed: "bg-emerald-100 text-emerald-800",
};
const GPS_TONES = {
  unpaid: "bg-stone-200 text-stone-700",
  partial: "bg-amber-100 text-amber-800",
  paid: "bg-emerald-100 text-emerald-800",
};

export default function AdminBookingsPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") || "";
  const [q, setQ] = useState(params.get("q") || "");
  const filters = useMemo(
    () => ({ status: status || undefined, q: params.get("q") || undefined }),
    [status, params],
  );
  useEffect(() => { setQ(params.get("q") || ""); }, [params]);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-bookings", filters],
    queryFn: () => api.get("/admin/bookings", { params: filters }).then((r) => r.data),
  });

  const setParam = (k, v) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    setParams(next, { replace: true });
  };

  const tabs = ["", "pending", "confirmed", "completed", "cancelled"];

  return (
    <AdminShell subtitle="Operations" title="Bookings">
      <div className="space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="inline-flex rounded-lg border border-stone-200 bg-white p-1 overflow-x-auto" data-testid="admin-bookings-status-tabs">
            {tabs.map((s) => (
              <button
                key={s}
                onClick={() => setParam("status", s)}
                data-testid={`admin-bookings-filter-${s || "all"}`}
                className={[
                  "px-3 py-1.5 text-sm rounded-md capitalize whitespace-nowrap",
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
              placeholder="Search reference code"
              className="w-full bg-transparent outline-none text-sm"
              data-testid="admin-bookings-search-input"
            />
          </label>
        </div>

        {isLoading ? (
          <div className="h-64 rounded-lg bg-stone-100 animate-pulse" />
        ) : !data?.bookings?.length ? (
          <div className="rounded-lg border border-dashed border-stone-200 p-10 text-center text-sm text-stone-500" data-testid="admin-bookings-empty">
            No bookings match those filters.
          </div>
        ) : (
          <>
            <div className="text-xs text-stone-500">
              {data.total} booking{data.total === 1 ? "" : "s"} · showing {data.bookings.length}
            </div>
            <Card>
              <CardContent className="p-0 overflow-x-auto">
                <table className="w-full text-sm min-w-[900px]" data-testid="admin-bookings-table">
                  <thead className="border-b border-stone-200 bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                    <tr>
                      <th className="px-4 py-3 text-left">Reference</th>
                      <th className="px-4 py-3 text-left">Agent</th>
                      <th className="px-4 py-3 text-left">Package</th>
                      <th className="px-4 py-3 text-left">Status</th>
                      <th className="px-4 py-3 text-left">Guest payment</th>
                      <th className="px-4 py-3 text-right">Pax</th>
                      <th className="px-4 py-3 text-right">Total</th>
                      <th className="px-4 py-3 text-right">Created</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.bookings.map((b) => (
                      <tr key={b.id} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`admin-booking-row-${b.id}`}>
                        <td className="px-4 py-3 font-mono text-xs">{b.reference_code}</td>
                        <td className="px-4 py-3">{b.agent?.display_name || "—"}</td>
                        <td className="px-4 py-3">
                          <div className="text-stone-900 truncate max-w-[220px]">{b.package?.title || "—"}</div>
                          <div className="text-xs text-stone-500">{b.package?.slug}</div>
                        </td>
                        <td className="px-4 py-3"><Badge className={STATUS_TONES[b.status]}>{b.status}</Badge></td>
                        <td className="px-4 py-3">
                          {b.guest_payment_status ? (
                            <Badge className={GPS_TONES[b.guest_payment_status]}>{b.guest_payment_status}</Badge>
                          ) : "—"}
                        </td>
                        <td className="px-4 py-3 text-right">{b.pax}</td>
                        <td className="px-4 py-3 text-right font-mono">{formatPHP(b.total_agent_cost)}</td>
                        <td className="px-4 py-3 text-right text-xs text-stone-500">{timeAgo(b.created_at)}</td>
                        <td className="px-4 py-3 text-right">
                          <Button asChild size="sm" variant="outline" data-testid={`admin-booking-open-${b.id}`}>
                            <Link to={`/admin/bookings/${b.id}`}>Open<ExternalLink size={12} className="ml-1" /></Link>
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
    </AdminShell>
  );
}
