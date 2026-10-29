import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import AgentShell from "@/components/agent/AgentShell";
import { Masked, PrivacyToggle } from "@/components/agent/PrivacyToggle";
import { api } from "@/lib/api";
import { formatPHP } from "@/lib/money";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Compass, Wallet, BookText, AlertTriangle, ArrowRight, CalendarPlus } from "lucide-react";
import { LedgerStatus } from "@/pages/agent/AgentLedgerPage";
import { usePrivacy } from "@/contexts/PrivacyContext";

const Stat = ({ label, value, hint, testid, masked }) => (
  <Card className="border-stone-200">
    <CardContent className="p-5">
      <div className="text-[11px] uppercase tracking-[0.2em] text-stone-500">{label}</div>
      <div className="font-display text-3xl mt-2 text-stone-900">
        {masked ? <Masked testid={testid}>{value}</Masked> : <span data-testid={testid}>{value}</span>}
      </div>
      {hint ? <div className="text-xs text-stone-500 mt-1">{hint}</div> : null}
    </CardContent>
  </Card>
);

const QuickLink = ({ to, icon: Icon, title, text, testid }) => (
  <Link
    to={to} data-testid={testid}
    className="group flex items-start gap-3 rounded-xl border border-stone-200 bg-white p-4 transition-colors hover:border-teal-700"
  >
    <div className="rounded-lg bg-teal-50 p-2 text-teal-800"><Icon size={18} /></div>
    <div className="flex-1 min-w-0">
      <div className="font-medium text-stone-900">{title}</div>
      <div className="text-xs text-stone-500 mt-0.5">{text}</div>
    </div>
    <ArrowRight size={16} className="text-stone-400 transition-transform group-hover:translate-x-1" />
  </Link>
);

const RecentLedger = ({ rows }) => (
  <Card className="border-stone-200">
    <CardContent className="p-0">
      <div className="flex items-center justify-between px-5 py-4 border-b border-stone-100">
        <div className="font-medium">Recent bookings</div>
        <Link to="/agent/bookings" className="text-xs text-teal-800 hover:underline" data-testid="dashboard-view-ledger">View all</Link>
      </div>
      {rows.length === 0 ? (
        <div className="px-5 py-8 text-sm text-stone-500" data-testid="dashboard-no-bookings">No bookings yet.</div>
      ) : rows.map((r) => (
        <div key={r.id} className="flex items-center justify-between gap-3 px-5 py-3 border-b border-stone-100 last:border-0" data-testid={`dashboard-ledger-row-${r.id}`}>
          <div className="min-w-0">
            <div className="text-sm font-medium truncate">{r.description}</div>
            <div className="text-xs text-stone-500 font-mono">{r.booking_ref}</div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span className="text-sm font-medium"><Masked>{formatPHP(r.earned)}</Masked></span>
            <LedgerStatus status={r.status} />
          </div>
        </div>
      ))}
    </CardContent>
  </Card>
);

export default function AgentDashboardPage() {
  const { hidden } = usePrivacy();
  const { data, isLoading } = useQuery({
    queryKey: ["agent-dashboard"],
    queryFn: () => api.get("/agent/dashboard").then((r) => r.data),
  });

  return (
    <AgentShell subtitle="Overview" title={data ? `Welcome back, ${data.agent.display_name}` : "Dashboard"}>
      <div className="space-y-8 max-w-6xl min-w-0" data-testid="agent-dashboard">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-xl border border-teal-200 bg-teal-50/60 p-4">
          <div className="text-sm text-teal-900">
            <b>Customer view</b> hides your net cost, markup and earnings so a customer can look at your screen safely.
          </div>
          <PrivacyToggle testid="dashboard-privacy-toggle" />
        </div>

        {isLoading || !data ? (
          <div className="h-40 rounded-xl bg-stone-100 animate-pulse" />
        ) : (
          <>
            {data.packages_needing_markup > 0 && !hidden ? (
              <Alert className="border-amber-300 bg-amber-50" data-testid="dashboard-markup-alert">
                <AlertTriangle className="h-4 w-4 text-amber-700" />
                <AlertDescription className="text-amber-900 text-sm">
                  {data.packages_needing_markup} of {data.packages_published} packages can't be sold yet — set or fix your markup.{" "}
                  <Link to="/agent/catalog" className="underline font-medium">Open catalog</Link>
                </AlertDescription>
              </Alert>
            ) : null}

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Booking balance" value={formatPHP(data.booking_balance)} testid="dashboard-booking-balance" masked hint="Funds for net-cost bookings" />
              <Stat label="Total earned" value={formatPHP(data.total_earned)} testid="dashboard-total-earned" masked hint="Markup + bonus commission" />
              <Stat label="Bookings" value={data.bookings_total} testid="dashboard-bookings-total" hint={`${data.bookings_by_status.confirmed || 0} confirmed · ${data.bookings_by_status.pending || 0} pending`} />
              <Stat label="Pending top-ups" value={data.pending_fund_requests} testid="dashboard-pending-topups" hint="Awaiting admin approval" />
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
              <div className="lg:col-span-3 min-w-0"><RecentLedger rows={data.recent_ledger} /></div>
              <div className="lg:col-span-2 space-y-3 min-w-0">
                <QuickLink to="/agent/bookings/new" icon={CalendarPlus} title="New booking" text="Book a package for a customer" testid="quick-link-new-booking" />
                <QuickLink to="/agent/catalog" icon={Compass} title="Package catalog" text={hidden ? "Browse packages and prices" : `Set your markup (${formatPHP(data.markup_bounds.min)} – ${formatPHP(data.markup_bounds.max)} per pax)`} testid="quick-link-catalog" />
                <QuickLink to="/agent/top-ups" icon={Wallet} title="Request a top-up" text="Add funds to your booking balance" testid="quick-link-topups" />
                <QuickLink to="/agent/ledger" icon={BookText} title="Earnings ledger" text="Every booking, cost and profit" testid="quick-link-ledger" />
              </div>
            </div>
          </>
        )}
      </div>
    </AgentShell>
  );
}
