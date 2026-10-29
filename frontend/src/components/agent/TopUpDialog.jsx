import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import { formatPHP } from "@/lib/money";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

export const TopUpDialog = ({ bounds, onClose }) => {
  const qc = useQueryClient();
  const [form, setForm] = useState({ amount: "", reference_no: "", note: "" });
  const [busy, setBusy] = useState(false);
  const n = parseFloat(form.amount);
  const valid = !Number.isNaN(n) && n >= parseFloat(bounds.min) && n <= parseFloat(bounds.max);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async () => {
    setBusy(true);
    try {
      await api.post("/agent/fund-requests", form);
      toast.success("Top-up request sent for approval.");
      qc.invalidateQueries({ queryKey: ["agent-fund-requests"] });
      qc.invalidateQueries({ queryKey: ["agent-dashboard"] });
      onClose();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent data-testid="topup-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Request a top-up</DialogTitle>
          <DialogDescription>Between {formatPHP(bounds.min)} and {formatPHP(bounds.max)} per request.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label htmlFor="tu-amount">Amount (PHP)</Label>
            <Input id="tu-amount" type="number" step="0.01" value={form.amount} onChange={set("amount")} data-testid="topup-amount-input" autoFocus />
            {form.amount !== "" && !valid ? (
              <div className="text-xs text-red-600 mt-1" data-testid="topup-amount-error">Amount is outside the allowed range.</div>
            ) : null}
          </div>
          <div>
            <Label htmlFor="tu-ref">Deposit reference no.</Label>
            <Input id="tu-ref" maxLength={120} value={form.reference_no} onChange={set("reference_no")} data-testid="topup-reference-input" />
          </div>
          <div>
            <Label htmlFor="tu-note">Note (optional)</Label>
            <Textarea id="tu-note" maxLength={400} value={form.note} onChange={set("note")} data-testid="topup-note-input" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="topup-cancel">Cancel</Button>
          <Button onClick={submit} disabled={!valid || busy} className="bg-teal-800 hover:bg-teal-900" data-testid="topup-submit">
            {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}Submit request
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
