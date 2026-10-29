import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AgentShell from "@/components/agent/AgentShell";
import { TopUpDialog } from "@/components/agent/TopUpDialog";
import { Masked } from "@/components/agent/PrivacyToggle";
import { api } from "@/lib/api";
import { formatPHP } from "@/lib/money";
import { timeAgo } from "@/lib/admin";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Plus } from "lucide-react";

const TONES = {
  pending: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-700",
};

const RequestRow = ({ r }) => (
  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 px-5 py-4 border-b border-stone-100 last:border-0 text-sm" data-testid={`topup-row-${r.id}`}>
    <div className="font-medium" ><Masked testid={`topup-amount-${r.id}`}>{formatPHP(r.amount)}</Masked></div>
    <div className="sm:order-last text-right sm:text-left">
      <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium capitalize ${TONES[r.status]}`} data-testid={`topup-status-${r.id}`}>{r.status}</span>
    </div>
    <div className="text-stone-600 truncate">{r.reference_no || "—"}</div>
    <div className="text-stone-500 truncate col-span-2 sm:col-span-1">{r.decision_note || r.note || ""}</div>
    <div className="text-stone-500 text-xs sm:text-sm">{timeAgo(r.created_at)}</div>
  </div>
);

export default function AgentFundRequestsPage() {
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["agent-fund-requests"],
    queryFn: () => api.get("/agent/fund-requests").then((r) => r.data),
  });
  const rows = data?.fund_requests || [];

  return (
    <AgentShell subtitle="Wallet" title="Top-up requests"
      actions={<Button onClick={() => setOpen(true)} className="bg-teal-800 hover:bg-teal-900" data-testid="topup-new-button"><Plus size={14} className="mr-1" />New top-up</Button>}>
      <div className="max-w-5xl space-y-4">
        <p className="text-sm text-stone-600">
          Deposit to our account first, then file a request with the deposit reference. Your booking balance is credited once an admin approves it.
        </p>
        <Card className="border-stone-200">
          <CardContent className="p-0">
            <div className="hidden sm:grid grid-cols-5 gap-2 px-5 py-3 border-b border-stone-200 text-[11px] uppercase tracking-widest text-stone-500">
              <div>Amount</div><div>Reference</div><div>Note</div><div>Filed</div><div>Status</div>
            </div>
            {isLoading ? <div className="h-24 animate-pulse bg-stone-50" /> : rows.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-stone-500" data-testid="topup-empty">No top-up requests yet.</div>
            ) : rows.map((r) => <RequestRow key={r.id} r={r} />)}
          </CardContent>
        </Card>
      </div>
      {open && data ? <TopUpDialog bounds={data.topup_bounds} onClose={() => setOpen(false)} /> : null}
    </AgentShell>
  );
}
