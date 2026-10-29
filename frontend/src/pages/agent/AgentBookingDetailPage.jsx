import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import AgentShell from "@/components/agent/AgentShell";
import { usePrivacy } from "@/contexts/PrivacyContext";
import { LedgerStatus } from "@/pages/agent/AgentLedgerPage";
import { fmtDate } from "@/pages/agent/AgentBookingsPage";
import { api, formatApiError } from "@/lib/api";
import { downloadQuote } from "@/lib/quote";
import { formatPHP } from "@/lib/money";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowLeft, FileDown, Loader2 } from "lucide-react";
import { toast } from "sonner";

const Line = ({ label, value, strong, testid }) => (
  <div className={`flex justify-between text-sm ${strong ? "font-semibold text-stone-900 border-t border-stone-200 pt-2" : "text-stone-600"}`}>
    <span>{label}</span><span data-testid={testid}>{value}</span>
  </div>
);

const Money = ({ b }) => {
  const { hidden } = usePrivacy();
  return (
    <Card className="border-stone-200"><CardContent className="p-5 space-y-2">
      <Line label="Price per person" value={formatPHP(b.unit_retail_price)} />
      <Line label={`Customer pays (${b.pax} pax)`} value={formatPHP(b.total_retail_price)} strong testid="booking-total-retail" />
      {!hidden ? (
        <div className="pt-3 space-y-2" data-testid="booking-agent-split">
          <Line label="Net cost charged to balance" value={formatPHP(b.total_net_cost)} testid="booking-net-cost" />
          <Line label="Your markup" value={formatPHP(b.total_markup)} />
          <Line label="Bonus commission" value={formatPHP(b.total_bonus_commission)} />
          <Line label="You earn" value={formatPHP(b.earned)} strong testid="booking-earned" />
        </div>
      ) : null}
    </CardContent></Card>
  );
};

const STATUS_HINT = {
  pending: "Waiting for Biyahe'Ta Bai to confirm. Contact us if you need to cancel.",
  confirmed: "Confirmed. To cancel, contact Biyahe'Ta Bai.",
  cancelled: "Cancelled by Biyahe'Ta Bai.",
  completed: "Trip completed.",
};

export default function AgentBookingDetailPage() {
  const { id } = useParams();
  const [busy, setBusy] = useState(false);
  const { data: b, isLoading, error } = useQuery({
    queryKey: ["agent-booking", id],
    queryFn: () => api.get(`/agent/bookings/${id}`).then((r) => r.data.booking),
  });

  const quote = async () => {
    setBusy(true);
    const err = await downloadQuote({ method: "get", url: `/agent/bookings/${id}/quote.pdf` });
    setBusy(false);
    if (err) toast.error(err); else toast.success("Quote downloaded.");
  };

  return (
    <AgentShell subtitle="Booking" title={b?.reference_code || "Booking"}
      actions={<>
        <Link to="/agent/bookings" data-testid="booking-back-link"><Button variant="ghost" size="sm"><ArrowLeft size={14} className="mr-1" />Bookings</Button></Link>
        {b ? <Button variant="outline" size="sm" onClick={quote} disabled={busy} data-testid="booking-download-quote">
          {busy ? <Loader2 size={14} className="animate-spin mr-1" /> : <FileDown size={14} className="mr-1" />}Customer quote
        </Button> : null}
      </>}>
      {isLoading ? <div className="h-60 rounded-xl bg-stone-100 animate-pulse max-w-5xl" /> : error ? (
        <div className="text-sm text-red-600" data-testid="booking-error">{formatApiError(error)}</div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3 max-w-5xl" data-testid="agent-booking-detail">
          <div className="lg:col-span-2 space-y-4">
            <Card className="border-stone-200"><CardContent className="p-5 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div className="font-display text-xl">{b.package?.title}</div>
                <span data-testid="booking-status"><LedgerStatus status={b.status} /></span>
              </div>
              <p className="text-xs text-stone-500">{STATUS_HINT[b.status]}</p>
              <div className="grid sm:grid-cols-3 gap-3 text-sm pt-2">
                <div><div className="text-[11px] uppercase tracking-widest text-stone-500">Customer</div>{b.customer?.name}</div>
                <div><div className="text-[11px] uppercase tracking-widest text-stone-500">Travel</div>{fmtDate(b.travel_start_date)} – {fmtDate(b.travel_end_date)}</div>
                <div><div className="text-[11px] uppercase tracking-widest text-stone-500">Customer payment</div><span className="capitalize">{b.guest_payment_status}</span></div>
              </div>
            </CardContent></Card>
            <Card className="border-stone-200"><CardContent className="p-5">
              <div className="font-medium mb-2">Travellers ({b.pax})</div>
              <ul className="text-sm space-y-1" data-testid="booking-travelers">
                {b.travelers.map((t, i) => <li key={i}>{t.full_name}{t.is_lead ? <span className="ml-2 text-[11px] text-teal-700">Lead</span> : null}</li>)}
              </ul>
              {b.notes ? <p className="text-sm text-stone-600 mt-3 whitespace-pre-line">{b.notes}</p> : null}
            </CardContent></Card>
          </div>
          <Money b={b} />
        </div>
      )}
    </AgentShell>
  );
}
