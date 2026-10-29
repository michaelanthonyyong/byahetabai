import { useQuery } from "@tanstack/react-query";
import AgentShell from "@/components/agent/AgentShell";
import { Masked } from "@/components/agent/PrivacyToggle";
import { api } from "@/lib/api";
import { formatPHP } from "@/lib/money";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableFooter,
} from "@/components/ui/table";

const TONES = {
  pending: "bg-amber-100 text-amber-800",
  confirmed: "bg-emerald-100 text-emerald-800",
  completed: "bg-sky-100 text-sky-800",
  cancelled: "bg-stone-200 text-stone-600",
};

export const LedgerStatus = ({ status }) => (
  <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium capitalize ${TONES[status] || "bg-stone-100"}`}>{status}</span>
);

const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString("en-PH", { year: "numeric", month: "short", day: "numeric" }) : "");

const EarningsTable = ({ data }) => (
  <Card className="border-stone-200"><CardContent className="p-0 overflow-x-auto">
    <Table data-testid="ledger-table">
      <TableHeader><TableRow>
        <TableHead>Date</TableHead><TableHead>Booking ID</TableHead><TableHead>Description</TableHead>
        <TableHead className="text-right">Net cost</TableHead><TableHead className="text-right">Customer paid</TableHead>
        <TableHead className="text-right">Earned profit / commission</TableHead><TableHead>Status</TableHead>
      </TableRow></TableHeader>
      <TableBody>
        {data.rows.length === 0 ? (
          <TableRow><TableCell colSpan={7} className="text-center text-stone-500 py-10" data-testid="ledger-empty">No bookings yet.</TableCell></TableRow>
        ) : data.rows.map((r) => (
          <TableRow key={r.id} data-testid={`ledger-row-${r.id}`} className={r.status === "cancelled" ? "text-stone-400" : ""}>
            <TableCell className="whitespace-nowrap">{fmtDate(r.date)}</TableCell>
            <TableCell className="font-mono text-xs whitespace-nowrap">{r.booking_ref}</TableCell>
            <TableCell className="min-w-[200px]">{r.description}</TableCell>
            <TableCell className="text-right"><Masked>{formatPHP(r.net_cost)}</Masked></TableCell>
            <TableCell className="text-right">{formatPHP(r.customer_paid)}</TableCell>
            <TableCell className="text-right">
              <Masked testid={`ledger-earned-${r.id}`}>
                <span className="font-medium text-emerald-700">{formatPHP(r.earned)}</span>
                <span className="block text-[11px] text-stone-500">{formatPHP(r.markup_profit)} markup + {formatPHP(r.bonus_commission)} bonus</span>
              </Masked>
            </TableCell>
            <TableCell><LedgerStatus status={r.status} /></TableCell>
          </TableRow>
        ))}
      </TableBody>
      {data.rows.length ? (
        <TableFooter><TableRow>
          <TableCell colSpan={3} className="font-medium">Totals (excluding cancelled)</TableCell>
          <TableCell className="text-right"><Masked>{formatPHP(data.totals.net_cost)}</Masked></TableCell>
          <TableCell className="text-right">{formatPHP(data.totals.customer_paid)}</TableCell>
          <TableCell className="text-right font-semibold"><Masked testid="ledger-total-earned">{formatPHP(data.totals.earned)}</Masked></TableCell>
          <TableCell />
        </TableRow></TableFooter>
      ) : null}
    </Table>
  </CardContent></Card>
);

const TYPE_LABELS = {
  TOP_UP: "Top-up", BOOKING_DEBIT: "Booking", BOOKING_REFUND: "Refund",
  ADJUSTMENT_CREDIT: "Adjustment (+)", ADJUSTMENT_DEBIT: "Adjustment (−)",
};

const WalletTable = () => {
  const { data, isLoading } = useQuery({
    queryKey: ["agent-transactions"],
    queryFn: () => api.get("/agent/transactions").then((r) => r.data),
  });
  const rows = data?.transactions || [];
  return (
    <Card className="border-stone-200"><CardContent className="p-0 overflow-x-auto">
      <Table data-testid="wallet-table">
        <TableHeader><TableRow>
          <TableHead>Date</TableHead><TableHead>Type</TableHead><TableHead>Note</TableHead>
          <TableHead className="text-right">Amount</TableHead><TableHead className="text-right">Balance after</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {isLoading ? null : rows.length === 0 ? (
            <TableRow><TableCell colSpan={5} className="text-center text-stone-500 py-10" data-testid="wallet-empty">No wallet activity yet.</TableCell></TableRow>
          ) : rows.map((t) => (
            <TableRow key={t.id} data-testid={`wallet-row-${t.id}`}>
              <TableCell className="whitespace-nowrap">{fmtDate(t.created_at)}</TableCell>
              <TableCell>{TYPE_LABELS[t.type] || t.type}</TableCell>
              <TableCell className="text-stone-500 min-w-[180px]">{t.note}</TableCell>
              <TableCell className={`text-right font-medium ${parseFloat(t.amount) >= 0 ? "text-emerald-700" : "text-red-600"}`}><Masked>{formatPHP(t.amount)}</Masked></TableCell>
              <TableCell className="text-right"><Masked>{formatPHP(t.balance_after)}</Masked></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </CardContent></Card>
  );
};

export default function AgentLedgerPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["agent-ledger"],
    queryFn: () => api.get("/agent/ledger").then((r) => r.data),
  });
  return (
    <AgentShell subtitle="Records" title="Ledger">
      <Tabs defaultValue="earnings" className="max-w-6xl">
        <TabsList>
          <TabsTrigger value="earnings" data-testid="ledger-tab-earnings">Earnings</TabsTrigger>
          <TabsTrigger value="wallet" data-testid="ledger-tab-wallet">Wallet activity</TabsTrigger>
        </TabsList>
        <TabsContent value="earnings" className="mt-4">
          {isLoading || !data ? <div className="h-40 rounded-xl bg-stone-100 animate-pulse" /> : <EarningsTable data={data} />}
        </TabsContent>
        <TabsContent value="wallet" className="mt-4"><WalletTable /></TabsContent>
      </Tabs>
    </AgentShell>
  );
}
