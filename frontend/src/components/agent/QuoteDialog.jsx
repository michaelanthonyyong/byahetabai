import { useState } from "react";
import { downloadQuote } from "@/lib/quote";
import { formatPHP } from "@/lib/money";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FileDown, Loader2, Link2 } from "lucide-react";
import { toast } from "sonner";
import { ShareLinkDialog } from "@/components/agent/ShareLinkDialog";

const today = () => new Date().toISOString().slice(0, 10);

export const QuoteDialog = ({ pkg, onClose }) => {
  const [form, setForm] = useState({ customer_name: "", pax: String(pkg.min_pax || 1), travel_date: "" });
  const [busy, setBusy] = useState(false);
  const [shareBody, setShareBody] = useState(null);
  const pax = parseInt(form.pax, 10);
  const paxOk = pax >= pkg.min_pax && pax <= pkg.max_pax;
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async () => {
    setBusy(true);
    const err = await downloadQuote({
      url: "/agent/quotes/pdf",
      body: { package_id: pkg.id, pax, customer_name: form.customer_name || null, travel_date: form.travel_date || null },
    });
    setBusy(false);
    if (err) { toast.error(err); return; }
    toast.success("Quote downloaded.");
    onClose();
  };

  if (shareBody) return <ShareLinkDialog body={shareBody} onClose={onClose} />;

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent data-testid="quote-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Customer quote · {pkg.title}</DialogTitle>
          <DialogDescription>A branded PDF showing only the final price per person. Valid for 7 days.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div><Label htmlFor="qt-name">Customer name</Label><Input id="qt-name" maxLength={120} value={form.customer_name} onChange={set("customer_name")} data-testid="quote-customer-name" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="qt-pax">Travellers ({pkg.min_pax}–{pkg.max_pax})</Label>
              <Input id="qt-pax" type="number" min={pkg.min_pax} max={pkg.max_pax} value={form.pax} onChange={set("pax")} data-testid="quote-pax" />
            </div>
            <div><Label htmlFor="qt-date">Travel date (optional)</Label><Input id="qt-date" type="date" min={today()} value={form.travel_date} onChange={set("travel_date")} data-testid="quote-travel-date" /></div>
          </div>
          <div className="rounded-lg bg-stone-50 border border-stone-200 p-3 text-sm flex justify-between font-semibold" data-testid="quote-total">
            <span>Total for customer</span><span>{paxOk ? formatPHP(parseFloat(pkg.retail_price) * pax) : "—"}</span>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="quote-cancel">Cancel</Button>
          <Button variant="outline" disabled={!paxOk} data-testid="quote-share-link"
            onClick={() => setShareBody({ kind: "quote", package_id: pkg.id, pax, customer_name: form.customer_name || null, travel_date: form.travel_date || null })}>
            <Link2 size={14} className="mr-1" />Get link
          </Button>
          <Button onClick={submit} disabled={!paxOk || busy} className="bg-teal-800 hover:bg-teal-900" data-testid="quote-download">
            {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : <FileDown size={14} className="mr-1" />}Download PDF
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
