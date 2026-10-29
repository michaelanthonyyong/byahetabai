import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import { formatPHP } from "@/lib/money";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

export const MarkupDialog = ({ pkg, bounds, onClose }) => {
  const qc = useQueryClient();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setValue(pkg?.markup_amount ? String(parseFloat(pkg.markup_amount)) : "");
  }, [pkg]);

  if (!pkg) return null;
  const n = parseFloat(value);
  const valid = !Number.isNaN(n) && n >= parseFloat(bounds.min) && n <= parseFloat(bounds.max);
  const retail = valid ? parseFloat(pkg.net_cost) + n : null;

  const save = async () => {
    setBusy(true);
    try {
      await api.put(`/agent/packages/${pkg.id}/markup`, { markup_amount: value });
      toast.success("Markup saved.");
      qc.invalidateQueries({ queryKey: ["agent-packages"] });
      qc.invalidateQueries({ queryKey: ["agent-package", pkg.id] });
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
      <DialogContent data-testid="markup-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Your markup · {pkg.title}</DialogTitle>
          <DialogDescription>
            Added on top of the net cost for each person. Allowed: {formatPHP(bounds.min)} – {formatPHP(bounds.max)} per pax.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="markup-input">Markup per pax (PHP)</Label>
            <Input
              id="markup-input" type="number" step="0.01" min={bounds.min} max={bounds.max}
              value={value} onChange={(e) => setValue(e.target.value)}
              data-testid="markup-input" autoFocus
            />
            {value !== "" && !valid ? (
              <div className="text-xs text-red-600 mt-1" data-testid="markup-input-error">
                Must be between {formatPHP(bounds.min)} and {formatPHP(bounds.max)}.
              </div>
            ) : null}
          </div>
          <div className="rounded-lg bg-stone-50 border border-stone-200 p-3 text-sm space-y-1">
            <Row label="Net cost" value={formatPHP(pkg.net_cost)} />
            <Row label="Your markup" value={valid ? formatPHP(n) : "—"} />
            <Row label="Bonus commission (from us)" value={formatPHP(pkg.bonus_commission)} />
            <div className="border-t border-stone-200 pt-1">
              <Row label="Customer pays (per pax)" value={retail != null ? formatPHP(retail) : "—"} strong testid="markup-preview-retail" />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="markup-cancel">Cancel</Button>
          <Button onClick={save} disabled={!valid || busy} className="bg-teal-800 hover:bg-teal-900" data-testid="markup-save">
            {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}Save markup
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const Row = ({ label, value, strong, testid }) => (
  <div className={`flex justify-between ${strong ? "font-semibold text-stone-900" : "text-stone-600"}`}>
    <span>{label}</span><span data-testid={testid}>{value}</span>
  </div>
);
