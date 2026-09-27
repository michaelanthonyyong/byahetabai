import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import PageShell from "@/components/public/PageShell";
import ListingCard from "@/components/public/ListingCard";
import { usePackages, useDestinations } from "@/hooks/public";
import { Search } from "lucide-react";

function ScopeTabs({ value, onChange }) {
  const options = [
    { v: "", label: "All tours" },
    { v: "international", label: "International" },
    { v: "domestic", label: "Domestic" },
  ];
  return (
    <div className="inline-flex rounded-full border border-brand-line bg-white p-1" data-testid="packages-scope-tabs">
      {options.map((o) => (
        <button
          key={o.v}
          onClick={() => onChange(o.v)}
          data-testid={`packages-scope-${o.v || "all"}`}
          className={[
            "px-4 py-2 text-sm font-medium rounded-full transition-colors",
            value === o.v ? "bg-brand-ocean text-white" : "text-brand-ink-soft hover:text-brand-ink",
          ].join(" ")}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export default function PackagesPage() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") || "");
  const scope = params.get("scope") || "";
  const destination = params.get("destination") || "";

  useEffect(() => { setQ(params.get("q") || ""); }, [params]);

  const filters = useMemo(
    () => ({ scope: scope || undefined, destination: destination || undefined, q: params.get("q") || undefined }),
    [scope, destination, params],
  );
  const { data, isLoading } = usePackages(filters);
  const dests = useDestinations();

  const setParam = (k, v) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    setParams(next, { replace: true });
  };

  const heading = scope === "domestic"
    ? "Domestic packages"
    : scope === "international"
      ? "International packages"
      : "All tour packages";

  return (
    <PageShell>
      <section className="mx-auto max-w-7xl px-6 py-14 md:py-20" data-testid="packages-page">
        <div className="text-[11px] uppercase tracking-[0.3em] text-brand-ocean mb-3">Tours</div>
        <h1 className="font-display text-4xl md:text-5xl text-brand-ink">{heading}</h1>
        <p className="mt-3 text-brand-ink-soft max-w-xl">
          Handpicked itineraries with flights, hotels and guided tours included where noted.
        </p>

        <div className="mt-8 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <ScopeTabs value={scope} onChange={(v) => setParam("scope", v)} />
          <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
            <label className="flex items-center gap-2 rounded-full bg-white border border-brand-line px-4 py-2 min-w-0">
              <Search size={16} className="text-brand-ink-soft shrink-0" />
              <input
                type="search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && setParam("q", q.trim())}
                placeholder="Search packages"
                className="bg-transparent outline-none w-full min-w-0 text-sm"
                data-testid="packages-search-input"
              />
            </label>
            <select
              value={destination}
              onChange={(e) => setParam("destination", e.target.value)}
              className="rounded-full bg-white border border-brand-line px-4 py-2 text-sm outline-none"
              data-testid="packages-destination-filter"
            >
              <option value="">All destinations</option>
              {(dests.data || [])
                .filter((d) => !scope || d.scope === scope)
                .map((d) => <option key={d.id} value={d.slug}>{d.name}</option>)}
            </select>
          </div>
        </div>

        <div className="mt-10">
          {isLoading ? (
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3" data-testid="packages-loading">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="aspect-[4/3] rounded-2xl bg-brand-mist animate-pulse" />
              ))}
            </div>
          ) : (data?.packages?.length ? (
            <>
              <div className="text-xs text-brand-ink-soft mb-4" data-testid="packages-count">
                Showing {data.packages.length} of {data.total} package{data.total === 1 ? "" : "s"}
              </div>
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3" data-testid="packages-grid">
                {data.packages.map((p) => <ListingCard key={p.id} pkg={p} />)}
              </div>
            </>
          ) : (
            <div
              className="rounded-2xl border border-dashed border-brand-line p-10 text-center text-brand-ink-soft"
              data-testid="packages-empty"
            >
              No packages match those filters.
            </div>
          ))}
        </div>
      </section>
    </PageShell>
  );
}
