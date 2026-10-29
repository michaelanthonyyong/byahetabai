import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AgentShell from "@/components/agent/AgentShell";
import { CustomerDialog } from "@/components/agent/CustomerDialog";
import { usePrivacy } from "@/contexts/PrivacyContext";
import { api, formatApiError } from "@/lib/api";
import { formatPHP } from "@/lib/money";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Plus } from "lucide-react";
import { toast } from "sonner";

const tomorrow = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const Summary = ({ pkg, pax, balance, busy, canSubmit, onSubmit }) => {
  const { hidden } = usePrivacy();
  const total = pkg ? parseFloat(pkg.retail_price) * pax : 0;
  const net = pkg ? parseFloat(pkg.net_cost) * pax : 0;
  const short = pkg && balance != null && net > parseFloat(balance);
  return (
    <Card className="border-stone-200 h-fit lg:sticky lg:top-6"><CardContent className="p-5 space-y-3">
      <div className="text-[11px] uppercase tracking-widest text-stone-500">Summary</div>
      <div className="flex justify-between text-sm"><span>Price per person</span><span>{pkg ? formatPHP(pkg.retail_price) : "—"}</span></div>
      <div className="flex justify-between font-semibold border-t border-stone-200 pt-2"><span>Customer pays</span><span data-testid="new-booking-total">{pkg ? formatPHP(total) : "—"}</span></div>
      {!hidden && pkg ? (
        <div className="space-y-1 text-sm text-stone-600 pt-2" data-testid="new-booking-agent-split">
          <div className="flex justify-between"><span>Charged to your balance</span><span data-testid="new-booking-net">{formatPHP(net)}</span></div>
          <div className="flex justify-between"><span>Balance available</span><span>{formatPHP(balance)}</span></div>
          <div className="flex justify-between text-emerald-700"><span>You earn</span><span>{formatPHP(total - net + parseFloat(pkg.bonus_commission) * pax)}</span></div>
        </div>
      ) : null}
      {short && !hidden ? <p className="text-xs text-red-600" data-testid="new-booking-insufficient">Not enough balance. Request a top-up first.</p> : null}
      {short && hidden ? <p className="text-xs text-stone-500" data-testid="new-booking-blocked-hint">This booking can't be placed right now. Turn off Customer view for details.</p> : null}
      <Button onClick={onSubmit} disabled={!canSubmit || busy || short} className="w-full bg-teal-800 hover:bg-teal-900" data-testid="new-booking-submit">
        {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}Confirm booking
      </Button>
      <p className="text-[11px] text-stone-500">Booking goes to Biyahe'Ta Bai for confirmation.</p>
    </CardContent></Card>
  );
};

export default function AgentNewBookingPage() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const [form, setForm] = useState({ package_id: params.get("package") || "", customer_id: "", pax: "1", date: "", notes: "" });
  const [names, setNames] = useState([]);
  const [addCustomer, setAddCustomer] = useState(false);
  const [busy, setBusy] = useState(false);
  const pkgs = useQuery({ queryKey: ["agent-packages"], queryFn: () => api.get("/agent/packages").then((r) => r.data) });
  const custs = useQuery({ queryKey: ["agent-customers"], queryFn: () => api.get("/agent/customers").then((r) => r.data.customers) });
  const dash = useQuery({ queryKey: ["agent-dashboard"], queryFn: () => api.get("/agent/dashboard").then((r) => r.data) });

  const bookable = useMemo(() => (pkgs.data?.packages || []).filter((p) => p.bookable), [pkgs.data]);
  const pkg = bookable.find((p) => p.id === form.package_id);
  const pax = parseInt(form.pax, 10) || 0;
  const paxOk = pkg && pax >= pkg.min_pax && pax <= pkg.max_pax;
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/agent/bookings", {
        customer_id: form.customer_id, package_id: form.package_id, pax,
        travel_start_date: form.date, traveler_names: names.slice(0, pax), notes: form.notes || null,
      });
      toast.success(`Booking ${data.booking.reference_code} created.`);
      ["agent-dashboard", "agent-bookings", "agent-ledger", "agent-transactions", "agent-customers"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      nav(`/agent/bookings/${data.booking.id}`);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AgentShell subtitle="Sell" title="New booking">
      <div className="grid gap-6 lg:grid-cols-3 max-w-5xl">
        <Card className="border-stone-200 lg:col-span-2"><CardContent className="p-5 space-y-4">
          <div>
            <Label>Package</Label>
            <Select value={form.package_id} onValueChange={set("package_id")}>
              <SelectTrigger data-testid="new-booking-package"><SelectValue placeholder="Choose a package" /></SelectTrigger>
              <SelectContent>{bookable.map((p) => <SelectItem key={p.id} value={p.id} data-testid={`new-booking-package-${p.id}`}>{p.title} · {formatPHP(p.retail_price)}/pax</SelectItem>)}</SelectContent>
            </Select>
            {pkgs.data && bookable.length < pkgs.data.packages.length ? (
              <p className="text-xs text-stone-500 mt-1">Only packages with a valid markup are listed.</p>
            ) : null}
          </div>
          <div>
            <Label>Customer</Label>
            <div className="flex gap-2">
              <Select value={form.customer_id} onValueChange={set("customer_id")}>
                <SelectTrigger data-testid="new-booking-customer"><SelectValue placeholder="Choose a customer" /></SelectTrigger>
                <SelectContent>{(custs.data || []).map((c) => <SelectItem key={c.id} value={c.id} data-testid={`new-booking-customer-${c.id}`}>{c.full_name}</SelectItem>)}</SelectContent>
              </Select>
              <Button variant="outline" onClick={() => setAddCustomer(true)} data-testid="new-booking-add-customer"><Plus size={14} /></Button>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="min-w-0">
              <Label htmlFor="nb-pax">Travellers{pkg ? ` (${pkg.min_pax}–${pkg.max_pax})` : ""}</Label>
              <Input id="nb-pax" type="number" min="1" value={form.pax} onChange={(e) => set("pax")(e.target.value)} data-testid="new-booking-pax" />
              {pkg && !paxOk ? <p className="text-xs text-red-600 mt-1" data-testid="new-booking-pax-error">Out of range for this package.</p> : null}
            </div>
            <div className="min-w-0"><Label htmlFor="nb-date">Travel date</Label><Input id="nb-date" type="date" min={tomorrow()} value={form.date} onChange={(e) => set("date")(e.target.value)} data-testid="new-booking-date" /></div>
          </div>
          {paxOk ? (
            <div className="space-y-2">
              <Label>Traveller names (first is lead; leave blank to use the customer)</Label>
              {Array.from({ length: pax }).map((_, i) => (
                <Input key={i} maxLength={120} placeholder={`Traveller ${i + 1}`} value={names[i] || ""}
                  onChange={(e) => setNames((n) => { const c = [...n]; c[i] = e.target.value; return c; })} data-testid={`new-booking-traveler-${i}`} />
              ))}
            </div>
          ) : null}
          <div><Label htmlFor="nb-notes">Notes</Label><Textarea id="nb-notes" maxLength={1000} value={form.notes} onChange={(e) => set("notes")(e.target.value)} data-testid="new-booking-notes" /></div>
        </CardContent></Card>
        <Summary pkg={paxOk ? pkg : null} pax={pax} balance={dash.data?.booking_balance} busy={busy}
          canSubmit={paxOk && form.customer_id && form.date} onSubmit={submit} />
      </div>
      {addCustomer ? <CustomerDialog onClose={() => setAddCustomer(false)} onSaved={(c) => set("customer_id")(c.id)} /> : null}
    </AgentShell>
  );
}
