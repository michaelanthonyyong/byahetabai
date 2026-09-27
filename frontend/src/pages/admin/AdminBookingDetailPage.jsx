import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api, formatApiError } from "@/lib/api";
import { formatPHP, humanAction, timeAgo } from "@/lib/admin";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";

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

const NEXT_STATUSES = {
  pending: [
    { v: "confirmed", label: "Confirm", tone: "default" },
    { v: "cancelled", label: "Cancel", tone: "destructive" },
  ],
  confirmed: [
    { v: "completed", label: "Mark completed", tone: "default" },
    { v: "cancelled", label: "Cancel", tone: "destructive" },
  ],
  cancelled: [],
  completed: [],
};

function ChangeStatusDialog({ booking, target, onDone }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [refund, setRefund] = useState(target.v === "cancelled");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setError("");
    setBusy(true);
    try {
      await api.patch(`/admin/bookings/${booking.id}/status`, {
        status: target.v, refund: target.v === "cancelled" ? refund : false, reason,
      });
      toast.success(`Booking ${target.v}`);
      setOpen(false); setReason(""); setRefund(target.v === "cancelled");
      onDone?.();
    } catch (err) {
      setError(formatApiError(err));
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant={target.tone === "destructive" ? "destructive" : "default"}
          data-testid={`admin-booking-action-${target.v}`}
        >{target.label}</Button>
      </DialogTrigger>
      <DialogContent data-testid={`admin-booking-dialog-${target.v}`}>
        <DialogHeader>
          <DialogTitle>{target.label} booking {booking.reference_code}</DialogTitle>
          <DialogDescription>
            {target.v === "cancelled"
              ? "This is a terminal state. You may optionally refund the agent's booking balance and any accrued commission will be reversed automatically."
              : "This transitions the booking. An audit entry will be recorded."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="rsn">Reason / note (optional)</Label>
            <Textarea id="rsn" rows={3} value={reason} onChange={(e) => setReason(e.target.value)}
              data-testid="admin-booking-reason-input" />
          </div>
          {target.v === "cancelled" ? (
            <label className="flex items-start gap-2 text-sm">
              <Checkbox checked={refund} onCheckedChange={(v) => setRefund(!!v)}
                data-testid="admin-booking-refund-checkbox" />
              <div>
                <div className="font-medium">Refund the agent's booking balance</div>
                <div className="text-xs text-stone-500">
                  Writes a BOOKING_REFUND transaction returning {formatPHP(booking.total_agent_cost)} to the agent.
                </div>
              </div>
            </label>
          ) : null}
          {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
        </div>
        <DialogFooter>
          <Button disabled={busy} onClick={submit}
            variant={target.tone === "destructive" ? "destructive" : "default"}
            data-testid="admin-booking-confirm-status">
            {busy ? "Saving…" : `Confirm ${target.label.toLowerCase()}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function GpsDialog({ booking, onDone }) {
  const [open, setOpen] = useState(false);
  const [gps, setGps] = useState(booking.guest_payment_status || "unpaid");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await api.patch(`/admin/bookings/${booking.id}/guest-payment-status`, { status: gps, note });
      toast.success("Payment status updated");
      setOpen(false); setNote("");
      onDone?.();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" data-testid="admin-booking-gps-button">Update guest payment</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Update guest payment status</DialogTitle>
          <DialogDescription>Informational only — no ledger impact.</DialogDescription></DialogHeader>
        <div className="grid grid-cols-3 rounded-lg border border-stone-200 bg-white p-1">
          {["unpaid","partial","paid"].map((v) => (
            <button key={v} type="button" onClick={() => setGps(v)}
              data-testid={`admin-booking-gps-option-${v}`}
              className={["py-1.5 text-sm rounded-md capitalize",
                gps === v ? "bg-stone-900 text-white" : "text-stone-600"].join(" ")}>
              {v}
            </button>
          ))}
        </div>
        <div className="space-y-2">
          <Label>Note</Label>
          <Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)}
            data-testid="admin-booking-gps-note-input" />
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={busy} data-testid="admin-booking-gps-submit">
            {busy ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function AdminBookingDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data: booking, isLoading, isError } = useQuery({
    queryKey: ["admin-booking", id],
    queryFn: () => api.get(`/admin/bookings/${id}`).then((r) => r.data.booking),
    enabled: !!id,
  });
  const { data: txnData } = useQuery({
    queryKey: ["admin-booking-txns", id],
    queryFn: () => api.get(`/admin/bookings/${id}/transactions`).then((r) => r.data),
    enabled: !!id,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["admin-booking", id] });
    qc.invalidateQueries({ queryKey: ["admin-booking-txns", id] });
    qc.invalidateQueries({ queryKey: ["admin-bookings"] });
    qc.invalidateQueries({ queryKey: ["admin-dashboard"] });
  };

  if (isLoading) {
    return <AdminShell title="Booking"><div className="h-64 rounded-lg bg-stone-100 animate-pulse" /></AdminShell>;
  }
  if (isError || !booking) {
    return (
      <AdminShell title="Booking">
        <div className="text-sm text-stone-600" data-testid="admin-booking-not-found">
          Booking not found. <Link className="underline" to="/admin/bookings">Back</Link>
        </div>
      </AdminShell>
    );
  }

  const nextStatuses = NEXT_STATUSES[booking.status] || [];

  return (
    <AdminShell
      subtitle={<Link to="/admin/bookings" className="inline-flex items-center gap-1 hover:underline"><ArrowLeft size={12}/>Bookings</Link>}
      title={booking.reference_code}
      actions={
        <div className="flex flex-wrap gap-2">
          <GpsDialog booking={booking} onDone={refresh} />
          {nextStatuses.map((t) => (
            <ChangeStatusDialog key={t.v} booking={booking} target={t} onDone={refresh} />
          ))}
        </div>
      }
    >
      <div className="space-y-6" data-testid="admin-booking-detail">
        <div className="grid gap-4 sm:grid-cols-4">
          <Card><CardHeader className="pb-2">
            <CardDescription>Status</CardDescription>
            <CardTitle><Badge className={STATUS_TONES[booking.status]}>{booking.status}</Badge></CardTitle>
          </CardHeader></Card>
          <Card><CardHeader className="pb-2">
            <CardDescription>Guest payment</CardDescription>
            <CardTitle><Badge className={GPS_TONES[booking.guest_payment_status]}>{booking.guest_payment_status}</Badge></CardTitle>
          </CardHeader></Card>
          <Card><CardHeader className="pb-2">
            <CardDescription>Pax</CardDescription>
            <CardTitle className="text-2xl">{booking.pax}</CardTitle>
          </CardHeader></Card>
          <Card><CardHeader className="pb-2">
            <CardDescription>Total agent cost</CardDescription>
            <CardTitle className="text-2xl" data-testid="admin-booking-total">{formatPHP(booking.total_agent_cost)}</CardTitle>
          </CardHeader></Card>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader><CardTitle>Booking</CardTitle></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2 text-sm">
              <div><div className="text-xs text-stone-500 mb-1">Agent</div>
                <div className="font-medium">{booking.agent?.display_name || "—"}</div>
                <div className="text-xs text-stone-500">{booking.agent?.email || ""}</div>
              </div>
              <div><div className="text-xs text-stone-500 mb-1">Customer</div>
                <div className="font-medium">{booking.customer?.name || "—"}</div>
              </div>
              <div className="sm:col-span-2"><div className="text-xs text-stone-500 mb-1">Package</div>
                <Link to={`/packages/${booking.package?.slug}`} target="_blank"
                  className="font-medium hover:underline">{booking.package?.title}</Link>
                <div className="text-xs text-stone-500">{booking.package?.slug}</div>
              </div>
              <div><div className="text-xs text-stone-500 mb-1">Unit agent cost</div>
                <div className="font-mono">{formatPHP(booking.unit_agent_cost)}</div>
              </div>
              <div><div className="text-xs text-stone-500 mb-1">Unit commission</div>
                <div className="font-mono">{formatPHP(booking.unit_commission_amount)}</div>
              </div>
              <div><div className="text-xs text-stone-500 mb-1">Total guest price</div>
                <div className="font-mono">{formatPHP(booking.total_guest_price)}</div>
              </div>
              <div><div className="text-xs text-stone-500 mb-1">Total commission</div>
                <div className="font-mono">{formatPHP(booking.total_commission_amount)}</div>
              </div>
              {booking.notes ? (
                <div className="sm:col-span-2"><div className="text-xs text-stone-500 mb-1">Notes</div>
                  <div className="whitespace-pre-line text-stone-700">{booking.notes}</div>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Travelers</CardTitle>
              <CardDescription>{(booking.travelers || []).length} on this booking</CardDescription></CardHeader>
            <CardContent className="p-0">
              {(booking.travelers || []).length === 0 ? (
                <div className="p-6 text-sm text-stone-500">None recorded.</div>
              ) : (
                <ul className="divide-y divide-stone-100" data-testid="admin-booking-travelers">
                  {booking.travelers.map((t) => (
                    <li key={t.id} className="px-4 py-3 text-sm">
                      <div className="font-medium">{t.full_name}{t.is_lead ? " · lead" : ""}</div>
                      {t.passport_no || t.nationality ? (
                        <div className="text-xs text-stone-500">
                          {t.passport_no ? `Passport ${t.passport_no}` : ""}
                          {t.passport_no && t.nationality ? " · " : ""}
                          {t.nationality || ""}
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader><CardTitle>Ledger for this booking</CardTitle>
            <CardDescription>All financial entries referencing this booking.</CardDescription></CardHeader>
          <CardContent className="p-0 overflow-x-auto">
            {!txnData?.transactions?.length ? (
              <div className="p-6 text-sm text-stone-500">No transactions.</div>
            ) : (
              <table className="w-full text-sm min-w-[720px]" data-testid="admin-booking-txns-table">
                <thead className="border-b border-stone-200 bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                  <tr>
                    <th className="px-4 py-3 text-left">When</th>
                    <th className="px-4 py-3 text-left">Type</th>
                    <th className="px-4 py-3 text-left">Account</th>
                    <th className="px-4 py-3 text-right">Amount</th>
                    <th className="px-4 py-3 text-right">Balance after</th>
                    <th className="px-4 py-3 text-left">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {txnData.transactions.map((t) => {
                    const pos = parseFloat(t.amount) >= 0;
                    return (
                      <tr key={t.id} className="border-t border-stone-100">
                        <td className="px-4 py-3 text-xs text-stone-500 whitespace-nowrap">{timeAgo(t.created_at)}</td>
                        <td className="px-4 py-3"><Badge variant="outline" className="font-mono text-[10px]">{t.type}</Badge></td>
                        <td className="px-4 py-3 capitalize text-stone-600">{t.account_kind}</td>
                        <td className={"px-4 py-3 text-right font-mono " + (pos ? "text-emerald-700" : "text-red-700")}>
                          {pos ? "+" : ""}{formatPHP(t.amount)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono">{formatPHP(t.balance_after)}</td>
                        <td className="px-4 py-3 text-xs text-stone-500 max-w-[240px] truncate">{t.note || "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Status history</CardTitle></CardHeader>
          <CardContent className="p-0">
            {(booking.status_history || []).length === 0 ? (
              <div className="p-6 text-sm text-stone-500">No history.</div>
            ) : (
              <ul className="divide-y divide-stone-100" data-testid="admin-booking-history">
                {booking.status_history.map((h) => (
                  <li key={h.id} className="flex items-start justify-between gap-4 px-6 py-3">
                    <div>
                      <div className="text-sm">
                        {h.from_status ? <><Badge variant="outline" className="mr-1">{h.from_status}</Badge>→ </> : null}
                        <Badge className={STATUS_TONES[h.to_status]}>{h.to_status}</Badge>
                      </div>
                      {h.note ? <div className="mt-1 text-xs text-stone-500">{h.note}</div> : null}
                    </div>
                    <div className="text-[10px] uppercase tracking-widest text-stone-400 shrink-0">
                      {timeAgo(h.changed_at)}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </AdminShell>
  );
}
