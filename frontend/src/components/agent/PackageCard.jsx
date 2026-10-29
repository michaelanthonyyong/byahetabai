import { Link } from "react-router-dom";
import { usePrivacy } from "@/contexts/PrivacyContext";
import { formatPHP } from "@/lib/money";
import { Button } from "@/components/ui/button";
import { MapPin, Pencil } from "lucide-react";

const STATE = {
  ok: { label: "Ready to sell", cls: "bg-emerald-100 text-emerald-800" },
  unset: { label: "Set your markup", cls: "bg-amber-100 text-amber-800" },
  out_of_range: { label: "Markup out of range", cls: "bg-red-100 text-red-700" },
};

export const MarkupBadge = ({ status, testid }) => {
  const s = STATE[status] || STATE.unset;
  return <span data-testid={testid} className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${s.cls}`}>{s.label}</span>;
};

export const PriceBreakdown = ({ pkg }) => (
  <div className="space-y-1 text-sm">
    <div className="flex justify-between text-stone-600"><span>Net cost</span><span data-testid={`pkg-net-${pkg.id}`}>{formatPHP(pkg.net_cost)}</span></div>
    <div className="flex justify-between text-stone-600"><span>Your markup</span><span data-testid={`pkg-markup-${pkg.id}`}>{pkg.markup_amount != null ? formatPHP(pkg.markup_amount) : "—"}</span></div>
    <div className="flex justify-between text-stone-600"><span>Bonus commission</span><span>{formatPHP(pkg.bonus_commission)}</span></div>
    <div className="flex justify-between font-semibold text-stone-900 border-t border-stone-200 pt-1">
      <span>Customer pays</span><span data-testid={`pkg-retail-${pkg.id}`}>{pkg.retail_price != null ? formatPHP(pkg.retail_price) : "—"}</span>
    </div>
  </div>
);

export const RetailOnly = ({ pkg }) => (
  <div className="flex items-end justify-between">
    <span className="text-xs uppercase tracking-widest text-stone-500">Price per person</span>
    <span className="font-display text-2xl text-stone-900" data-testid={`pkg-retail-only-${pkg.id}`}>
      {pkg.bookable ? formatPHP(pkg.retail_price) : <span className="text-sm text-stone-400">Not available</span>}
    </span>
  </div>
);

export const PackageCard = ({ pkg, onEdit }) => {
  const { hidden } = usePrivacy();
  return (
    <div className="group overflow-hidden rounded-2xl border border-stone-200 bg-white flex flex-col" data-testid={`catalog-card-${pkg.id}`}>
      <Link to={`/agent/catalog/${pkg.id}`} className="relative block aspect-[16/10] overflow-hidden bg-stone-100" data-testid={`catalog-card-link-${pkg.id}`}>
        {pkg.cover_image_url ? (
          <img src={pkg.cover_image_url} alt={pkg.title} className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
        ) : null}
        {!hidden ? <div className="absolute left-3 top-3"><MarkupBadge status={pkg.markup_status} testid={`catalog-card-status-${pkg.id}`} /></div> : null}
      </Link>
      <div className="flex-1 p-5 flex flex-col gap-4">
        <div>
          <div className="flex items-center gap-1 text-xs text-stone-500"><MapPin size={12} />{pkg.destination?.name} · {pkg.duration_days}D{pkg.duration_nights}N</div>
          <div className="font-display text-lg text-stone-900 mt-1 leading-snug">{pkg.title}</div>
        </div>
        <div className="mt-auto">{hidden ? <RetailOnly pkg={pkg} /> : <PriceBreakdown pkg={pkg} />}</div>
        {!hidden ? (
          <Button variant="outline" onClick={() => onEdit(pkg)} data-testid={`catalog-edit-markup-${pkg.id}`} className="w-full">
            <Pencil size={14} className="mr-1" />{pkg.markup_amount != null ? "Edit markup" : "Set markup"}
          </Button>
        ) : null}
      </div>
    </div>
  );
};
