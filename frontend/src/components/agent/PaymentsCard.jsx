import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import { formatPHP } from "@/lib/money";
import { fmtDate } from "@/pages/agent/AgentBookingsPage";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { Plus, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";

export const METHODS = { cash: "Cash", gcash: "GCash", bank_transfer: "Bank transfer", card: "Card", other: "Other" };
const localToday = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const AddPaymentDialog = ({ bookingId, balanceDue, onClose }) => {
  const qc = useQueryClient();
  const [form, setForm] = useState({ amount: "", method: "cash", paid_on: localToday(), reference: "", note: "" });
  const [busy, setBusy] = useState(false);
  const n = parseFloat(form.amount);
  const valid = n > 0 && n <= parseFloat(balanceDue) && form.paid_on;
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const save = async () => {
    setBusy(true);
    try {
      await api.post(`/agent/bookings/${bookingId}/payments`, form);
      toast.success("Payment recorded.");
      ["agent-payments", "agent-booking", "agent-bookings", "agent-dashboard"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      onClose();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent data-testid="payment-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Record a customer payment</DialogTitle>
          <DialogDescription>Balance due: {formatPHP(balanceDue)}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="min-w-0">
            <Label htmlFor="pm-amount">Amount (PHP)</Label>
            <Input id="pm-amount" type="number" step="0.01" value={form.amount} onChange={set("amount")} data-testid="payment-amount-input" autoFocus />
            {form.amount && !(n > 0 && n <= parseFloat(balanceDue)) ? <p className="text-xs text-red-600 mt-1" data-testid="payment-amount-error">Must be more than 0 and no more than the balance due.</p> : null}
          </div>
          <div className="min-w-0">
            <Label>Method</Label>
            <Select value={form.method} onValueChange={(v) => setForm((f) => ({ ...f, method: v }))}>
              <SelectTrigger data-testid="payment-method-select"><SelectValue /></SelectTrigger>
              <SelectContent>{Object.entries(METHODS).map(([k, v]) => <SelectItem key={k} value={k} data-testid={`payment-method-${k}`}>{v}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="min-w-0"><Label htmlFor="pm-date">Paid on</Label><Input id="pm-date" type="date" max={localToday()} value={form.paid_on} onChange={set("paid_on")} data-testid="payment-date-input" /></div>
          <div className="min-w-0"><Label htmlFor="pm-ref">Reference (optional)</Label><Input id="pm-ref" maxLength={120} value={form.reference} onChange={set("reference")} data-testid="payment-reference-input" /></div>
          <div className="sm:col-span-2"><Label htmlFor="pm-note">Note (optional)</Label><Input id="pm-note" maxLength={400} value={form.note} onChange={set("note")} data-testid="payment-note-input" /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="payment-cancel">Cancel</Button>
          <Button onClick={save} disabled={!valid || busy} className="bg-teal-800 hover:bg-teal-900" data-testid="payment-save">
            {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}Save payment
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const Totals = ({ d }) => (
  <div className="grid grid-cols-3 gap-3 text-sm">
    <div><div className="text-[11px] uppercase tracking-widest text-stone-500">Total</div><div className="font-medium">{formatPHP(d.total_due)}</div></div>
    <div><div className="text-[11px] uppercase tracking-widest text-stone-500">Paid</div><div className="font-medium text-emerald-700" data-testid="payments-amount-paid">{formatPHP(d.amount_paid)}</div></div>
    <div><div className="text-[11px] uppercase tracking-widest text-stone-500">Balance due</div><div className={`font-medium ${parseFloat(d.balance_due) > 0 ? "text-amber-700" : "text-stone-900"}`} data-testid="payments-balance-due">{formatPHP(d.balance_due)}</div></div>
  </div>
);

export const PaymentsCard = ({ bookingId, cancelled }) => {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const { data } = useQuery({
    queryKey: ["agent-payments", bookingId],
    queryFn: () => api.get(`/agent/bookings/${bookingId}/payments`).then((r) => r.data),
  });
  const remove = async (p) => {
    if (!window.confirm(`Remove the ${formatPHP(p.amount)} payment?`)) return;
    try {
      await api.delete(`/agent/bookings/${bookingId}/payments/${p.id}`);
      toast.success("Payment removed.");
      ["agent-payments", "agent-booking", "agent-bookings", "agent-dashboard"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };
  if (!data) return <div className="h-32 rounded-xl bg-stone-100 animate-pulse" />;
  const canAdd = !cancelled && parseFloat(data.balance_due) > 0;
  return (
    <Card className="border-stone-200" data-testid="payments-card"><CardContent className="p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="font-medium">Customer payments</div>
        {canAdd ? <Button size="sm" variant="outline" onClick={() => setAdding(true)} data-testid="payment-add-button"><Plus size={14} className="mr-1" />Record payment</Button> : null}
      </div>
      <Totals d={data} />
      {data.payments.length === 0 ? (
        <p className="text-sm text-stone-500" data-testid="payments-empty">No payments recorded yet.</p>
      ) : (
        <ul className="divide-y divide-stone-100 text-sm" data-testid="payments-list">
          {data.payments.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-3 py-2" data-testid={`payment-row-${p.id}`}>
              <div className="min-w-0">
                <div className="font-medium">{formatPHP(p.amount)} · {METHODS[p.method] || p.method}</div>
                <div className="text-xs text-stone-500 truncate">{fmtDate(p.paid_on)}{p.reference ? ` · Ref ${p.reference}` : ""}{p.note ? ` · ${p.note}` : ""}</div>
              </div>
              <Button variant="ghost" size="sm" onClick={() => remove(p)} data-testid={`payment-delete-${p.id}`}><Trash2 size={14} /></Button>
            </li>
          ))}
        </ul>
      )}
      {adding ? <AddPaymentDialog bookingId={bookingId} balanceDue={data.balance_due} onClose={() => setAdding(false)} /> : null}
    </CardContent></Card>
  );
};
