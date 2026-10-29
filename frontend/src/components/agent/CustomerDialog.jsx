import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

const EMPTY = { first_name: "", last_name: "", email: "", phone: "", address: "", notes: "" };
const FIELDS = [
  ["first_name", "First name *", 80], ["last_name", "Last name *", 80],
  ["email", "Email", 120], ["phone", "Phone", 40],
];

export const CustomerDialog = ({ customer, onClose, onSaved }) => {
  const qc = useQueryClient();
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setForm(customer ? Object.fromEntries(Object.keys(EMPTY).map((k) => [k, customer[k] || ""])) : EMPTY);
  }, [customer]);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const valid = form.first_name.trim() && form.last_name.trim();

  const save = async () => {
    setBusy(true);
    const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() || null]));
    try {
      const { data } = customer
        ? await api.patch(`/agent/customers/${customer.id}`, body)
        : await api.post("/agent/customers", body);
      toast.success(customer ? "Customer updated." : "Customer added.");
      qc.invalidateQueries({ queryKey: ["agent-customers"] });
      qc.invalidateQueries({ queryKey: ["agent-customer"] });
      onSaved?.(data.customer);
      onClose();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent data-testid="customer-dialog">
        <DialogHeader><DialogTitle className="font-display">{customer ? "Edit customer" : "New customer"}</DialogTitle></DialogHeader>
        <div className="grid gap-3 sm:grid-cols-2">
          {FIELDS.map(([k, label, max]) => (
            <div key={k}>
              <Label htmlFor={`c-${k}`}>{label}</Label>
              <Input id={`c-${k}`} type={k === "email" ? "email" : "text"} maxLength={max} value={form[k]} onChange={set(k)} data-testid={`customer-${k}-input`} />
            </div>
          ))}
          <div className="sm:col-span-2"><Label htmlFor="c-address">Address</Label><Input id="c-address" maxLength={300} value={form.address} onChange={set("address")} data-testid="customer-address-input" /></div>
          <div className="sm:col-span-2"><Label htmlFor="c-notes">Notes</Label><Textarea id="c-notes" maxLength={1000} value={form.notes} onChange={set("notes")} data-testid="customer-notes-input" /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="customer-cancel">Cancel</Button>
          <Button onClick={save} disabled={!valid || busy} className="bg-teal-800 hover:bg-teal-900" data-testid="customer-save">
            {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}Save customer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
