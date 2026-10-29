import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import AgentShell from "@/components/agent/AgentShell";
import { MarkupBadge, PriceBreakdown, RetailOnly } from "@/components/agent/PackageCard";
import { MarkupDialog } from "@/components/agent/MarkupDialog";
import { usePrivacy } from "@/contexts/PrivacyContext";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowLeft, Check, X, Pencil } from "lucide-react";

const List = ({ items, icon: Icon, tone }) => (
  <ul className="space-y-1.5 text-sm text-stone-700">
    {items.map((t, i) => <li key={i} className="flex gap-2"><Icon size={14} className={`mt-0.5 shrink-0 ${tone}`} />{t}</li>)}
  </ul>
);

const Info = ({ pkg }) => (
  <div className="space-y-6">
    {pkg.summary ? <p className="text-stone-700 leading-relaxed">{pkg.summary}</p> : null}
    {pkg.highlights ? <div><h3 className="font-medium mb-1">Highlights</h3><p className="text-sm text-stone-600 whitespace-pre-line">{pkg.highlights}</p></div> : null}
    {pkg.itinerary ? <div><h3 className="font-medium mb-1">Itinerary</h3><p className="text-sm text-stone-600 whitespace-pre-line">{pkg.itinerary}</p></div> : null}
    <div className="grid sm:grid-cols-2 gap-6">
      {pkg.inclusions.length ? <div><h3 className="font-medium mb-2">Inclusions</h3><List items={pkg.inclusions} icon={Check} tone="text-emerald-600" /></div> : null}
      {pkg.exclusions.length ? <div><h3 className="font-medium mb-2">Exclusions</h3><List items={pkg.exclusions} icon={X} tone="text-red-500" /></div> : null}
    </div>
  </div>
);

export default function AgentPackageDetailPage() {
  const { id } = useParams();
  const { hidden } = usePrivacy();
  const [editing, setEditing] = useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: ["agent-package", id],
    queryFn: () => api.get(`/agent/packages/${id}`).then((r) => r.data),
  });
  const pkg = data?.package;

  return (
    <AgentShell subtitle={pkg?.destination?.name || "Package"} title={pkg?.title || "Package"}
      actions={<Link to="/agent/catalog" data-testid="package-back-link"><Button variant="ghost" size="sm"><ArrowLeft size={14} className="mr-1" />Catalog</Button></Link>}>
      {isLoading ? <div className="h-80 rounded-2xl bg-stone-100 animate-pulse" /> : error ? (
        <div className="text-sm text-red-600" data-testid="package-error">{formatApiError(error)}</div>
      ) : (
        <div className="grid gap-8 lg:grid-cols-3 max-w-6xl" data-testid="agent-package-detail">
          <div className="lg:col-span-2 space-y-6">
            {pkg.cover_image_url ? <img src={pkg.cover_image_url} alt={pkg.title} className="w-full aspect-[16/9] object-cover rounded-2xl" /> : null}
            <Info pkg={pkg} />
          </div>
          <Card className="border-stone-200 h-fit lg:sticky lg:top-6">
            <CardContent className="p-5 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-stone-500">{pkg.duration_days}D{pkg.duration_nights}N · {pkg.min_pax}–{pkg.max_pax} pax</span>
                {!hidden ? <MarkupBadge status={pkg.markup_status} testid="package-markup-status" /> : null}
              </div>
              {hidden ? <RetailOnly pkg={pkg} /> : <PriceBreakdown pkg={pkg} />}
              {!hidden ? (
                <Button onClick={() => setEditing(true)} className="w-full bg-teal-800 hover:bg-teal-900" data-testid="package-edit-markup">
                  <Pencil size={14} className="mr-1" />{pkg.markup_amount != null ? "Edit markup" : "Set markup"}
                </Button>
              ) : null}
              {!pkg.bookable && !hidden ? (
                <p className="text-xs text-amber-700" data-testid="package-not-bookable">
                  {pkg.markup_status === "out_of_range" ? "Your markup is outside the current allowed range. Update it to sell this package." : "Set a markup to start selling this package."}
                </p>
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}
      {editing && pkg ? <MarkupDialog pkg={pkg} bounds={data.markup_bounds} onClose={() => setEditing(false)} /> : null}
    </AgentShell>
  );
}
