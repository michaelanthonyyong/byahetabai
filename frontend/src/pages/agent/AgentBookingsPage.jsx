import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import AgentShell from "@/components/agent/AgentShell";
import { Masked } from "@/components/agent/PrivacyToggle";
import { usePrivacy } from "@/contexts/PrivacyContext";
import { LedgerStatus } from "@/pages/agent/AgentLedgerPage";
import { api } from "@/lib/api";
import { formatPHP } from "@/lib/money";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plus } from "lucide-react";

const TABS = ["", "pending", "confirmed", "completed", "cancelled", "owing"];
export const fmtDate = (iso) => (iso ? new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("en-PH", { year: "numeric", month: "short", day: "numeric" }) : "—");

export default function AgentBookingsPage() {
  const [params, setParams] = useSearchParams();
  const { hidden } = usePrivacy();
  const tab = params.get("payment") === "owing" ? "owing" : params.get("status") || "";
  const status = tab === "owing" ? "" : tab;
  const { data, isLoading } = useQuery({
    queryKey: ["agent-bookings", tab],
    queryFn: () => api.get("/agent/bookings", { params: tab === "owing" ? { payment: "owing" } : { status: status || undefined } }).then((r) => r.data.bookings),
  });
  const rows = data || [];

  return (
    <AgentShell subtitle="Sell" title="Bookings"
      actions={<Link to="/agent/bookings/new" data-testid="booking-new-button"><Button className="bg-teal-800 hover:bg-teal-900"><Plus size={14} className="mr-1" />New booking</Button></Link>}>
      <div className="max-w-6xl space-y-4">
        <div className="flex gap-1 overflow-x-auto rounded-full bg-stone-100 p-1 w-fit max-w-full">
          {TABS.map((t) => (
            <button key={t || "all"} onClick={() => setParams(t === "owing" ? { payment: "owing" } : t ? { status: t } : {}, { replace: true })} data-testid={`bookings-tab-${t || "all"}`}
              className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors ${tab === t ? "bg-white text-stone-900 shadow-sm" : "text-stone-500"}`}>
              {t === "owing" ? "Balance due" : t || "All"}
            </button>
          ))}
        </div>
        <Card className="border-stone-200"><CardContent className="p-0 overflow-x-auto">
          <Table data-testid="bookings-table">
            <TableHeader><TableRow>
              <TableHead>Booking ID</TableHead><TableHead>Customer</TableHead><TableHead>Package</TableHead>
              <TableHead>Travel</TableHead><TableHead className="text-right">Customer pays</TableHead>
              <TableHead className="text-right">Balance due</TableHead>
              {!hidden ? <TableHead className="text-right">Earned</TableHead> : null}<TableHead>Status</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {isLoading ? null : rows.length === 0 ? (
                <TableRow><TableCell colSpan={8} className="text-center py-10 text-stone-500" data-testid="bookings-empty">No bookings here yet.</TableCell></TableRow>
              ) : rows.map((b) => (
                <TableRow key={b.id} data-testid={`booking-row-${b.id}`}>
                  <TableCell className="font-mono text-xs whitespace-nowrap">
                    <Link to={`/agent/bookings/${b.id}`} className="text-teal-800 hover:underline" data-testid={`booking-link-${b.id}`}>{b.reference_code}</Link>
                  </TableCell>
                  <TableCell>{b.customer?.name}</TableCell>
                  <TableCell className="min-w-[180px]">{b.package?.title} · {b.pax} pax</TableCell>
                  <TableCell className="whitespace-nowrap">{fmtDate(b.travel_start_date)}</TableCell>
                  <TableCell className="text-right">{formatPHP(b.total_retail_price)}</TableCell>
                  <TableCell className={`text-right ${b.status !== "cancelled" && parseFloat(b.balance_due) > 0 ? "text-amber-700 font-medium" : "text-stone-400"}`} data-testid={`booking-balance-due-${b.id}`}>
                    {b.status === "cancelled" ? "—" : formatPHP(b.balance_due)}
                  </TableCell>
                  {!hidden ? <TableCell className="text-right text-emerald-700"><Masked>{formatPHP(b.earned)}</Masked></TableCell> : null}
                  <TableCell><LedgerStatus status={b.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent></Card>
      </div>
    </AgentShell>
  );
}
