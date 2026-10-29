import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AgentShell from "@/components/agent/AgentShell";
import { PackageCard } from "@/components/agent/PackageCard";
import { MarkupDialog } from "@/components/agent/MarkupDialog";
import { usePrivacy } from "@/contexts/PrivacyContext";
import { api } from "@/lib/api";
import { formatPHP } from "@/lib/money";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "ok", label: "Ready to sell" },
  { id: "attention", label: "Needs markup" },
];

export default function AgentCatalogPage() {
  const { hidden } = usePrivacy();
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [editing, setEditing] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ["agent-packages"],
    queryFn: () => api.get("/agent/packages").then((r) => r.data),
  });

  const bounds = data?.markup_bounds || { min: "0", max: "0" };
  const rows = (data?.packages || []).filter((p) => {
    if (q && !p.title.toLowerCase().includes(q.toLowerCase())) return false;
    if (filter === "ok") return p.markup_status === "ok";
    if (filter === "attention") return p.markup_status !== "ok";
    return true;
  });

  return (
    <AgentShell subtitle="Sell" title="Package catalog">
      <div className="space-y-6 max-w-6xl">
        {!hidden ? (
          <p className="text-sm text-stone-600" data-testid="catalog-bounds-note">
            Set your own markup on each package, between {formatPHP(bounds.min)} and {formatPHP(bounds.max)} per pax.
            A package can only be booked once its markup is set and within range.
          </p>
        ) : null}
        <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
          <div className="relative sm:w-80">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search packages" className="pl-8" data-testid="catalog-search" />
          </div>
          {!hidden ? (
            <div className="flex gap-1 rounded-full bg-stone-100 p-1">
              {FILTERS.map((f) => (
                <button
                  key={f.id} onClick={() => setFilter(f.id)} data-testid={`catalog-filter-${f.id}`}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${filter === f.id ? "bg-white text-stone-900 shadow-sm" : "text-stone-500"}`}
                >{f.label}</button>
              ))}
            </div>
          ) : null}
        </div>
        {isLoading ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => <div key={i} className="h-80 rounded-2xl bg-stone-100 animate-pulse" />)}
          </div>
        ) : rows.length === 0 ? (
          <div className="rounded-xl border border-dashed border-stone-300 p-10 text-center text-sm text-stone-500" data-testid="catalog-empty">
            No packages match.
          </div>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3" data-testid="catalog-grid">
            {rows.map((p) => <PackageCard key={p.id} pkg={p} onEdit={setEditing} />)}
          </div>
        )}
      </div>
      {editing ? <MarkupDialog pkg={editing} bounds={bounds} onClose={() => setEditing(null)} /> : null}
    </AgentShell>
  );
}
