import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import PageShell from "@/components/public/PageShell";
import SectionHeader from "@/components/public/SectionHeader";
import ListingCard from "@/components/public/ListingCard";
import DestinationTile from "@/components/public/DestinationTile";
import { usePackages, useDestinations, useBrand } from "@/hooks/public";
import { Search } from "lucide-react";

const HERO_IMAGE =
  "https://images.unsplash.com/photo-1542051841857-5f90071e7989?q=80&w=1800";

function HeroSearch() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [scope, setScope] = useState("");
  const submit = (e) => {
    e.preventDefault();
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    if (scope) params.set("scope", scope);
    navigate(`/packages${params.toString() ? `?${params}` : ""}`);
  };
  return (
    <form
      onSubmit={submit}
      data-testid="hero-search-form"
      className="mt-10 md:mt-14 grid gap-2 rounded-2xl bg-white/95 backdrop-blur p-3 md:p-2 md:grid-cols-[1fr,180px,auto] md:items-center shadow-2xl shadow-black/20"
    >
      <div className="flex items-center gap-2 px-3 md:px-4">
        <Search size={18} className="text-brand-ink-soft shrink-0" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Where do you want to go?"
          className="w-full bg-transparent py-3 outline-none placeholder:text-brand-ink-soft/70"
          data-testid="hero-search-query"
        />
      </div>
      <select
        value={scope}
        onChange={(e) => setScope(e.target.value)}
        className="mx-3 md:mx-0 md:border-l md:border-brand-line bg-transparent py-3 px-3 outline-none text-brand-ink"
        data-testid="hero-search-scope"
      >
        <option value="">All tours</option>
        <option value="domestic">Domestic</option>
        <option value="international">International</option>
      </select>
      <button
        type="submit"
        className="rounded-xl bg-brand-sunset px-6 py-3 font-semibold text-white hover:bg-brand-sunset/90 transition-colors"
        data-testid="hero-search-submit"
      >
        Search
      </button>
    </form>
  );
}

export default function HomePage() {
  const { data: brand } = useBrand();
  const featured = usePackages({ page_size: 8 });
  const domestic = usePackages({ scope: "domestic", page_size: 4 });
  const destinations = useDestinations({ featured: true });

  return (
    <PageShell heroTransparent>
      {/* HERO */}
      <section className="relative brand-grain" data-testid="home-hero">
        <div className="absolute inset-0">
          <img src={HERO_IMAGE} alt="" className="h-full w-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-b from-brand-ink/60 via-brand-ink/40 to-brand-ink/70" />
        </div>
        <div className="relative mx-auto max-w-7xl px-6 pt-40 pb-24 md:pt-48 md:pb-32">
          <div className="max-w-2xl">
            <div className="text-sm font-medium tracking-[0.12em] text-brand-sunset-soft mb-4">
              {brand?.name || "eNaviga"}
            </div>
            <h1 className="font-display text-5xl md:text-6xl lg:text-7xl text-white leading-[1.05]" data-testid="home-hero-headline">
              {brand?.tagline || "Go. Explore. Discover."}
            </h1>
            <p className="mt-5 text-lg text-white/85 max-w-xl">
              Experience the best of local and international travel with eNaviga.
            </p>
            <HeroSearch />
          </div>
        </div>
      </section>

      {/* INTERNATIONAL TOURS */}
      <section className="mx-auto max-w-7xl px-6 py-20" data-testid="home-international-section">
        <SectionHeader
          eyebrow="International"
          title="International tour packages"
          description="Choose from our vetted selection of island and continent adventures."
          actionHref="/packages?scope=international"
          actionLabel="See all →"
        />
        {featured.isLoading ? (
          <SkeletonGrid />
        ) : (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4" data-testid="home-international-grid">
            {(featured.data?.packages || [])
              .filter((p) => p.destination?.scope === "international")
              .slice(0, 4)
              .map((p) => (
                <ListingCard key={p.id} pkg={p} />
              ))}
          </div>
        )}
      </section>

      {/* EXPLORE BY DESTINATION */}
      <section className="bg-white/50 border-y border-brand-line" data-testid="home-destinations-section">
        <div className="mx-auto max-w-7xl px-6 py-20">
          <SectionHeader
            eyebrow="Where next?"
            title="Explore by destination"
            description="Our most popular getaways, across the islands and beyond."
            actionHref="/destinations"
          />
          {destinations.isLoading ? (
            <SkeletonGrid />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="home-destinations-grid">
              {(destinations.data || []).map((d) => (
                <DestinationTile key={d.id} destination={d} />
              ))}
            </div>
          )}
        </div>
      </section>

      {/* DOMESTIC TOURS */}
      <section className="mx-auto max-w-7xl px-6 py-20" data-testid="home-domestic-section">
        <SectionHeader
          eyebrow="Philippines"
          title="Domestic favourites"
          description="Discover the best of home — from Cebu to Palawan and beyond."
          actionHref="/packages?scope=domestic"
        />
        {domestic.isLoading ? (
          <SkeletonGrid />
        ) : domestic.data?.packages?.length ? (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4" data-testid="home-domestic-grid">
            {domestic.data.packages.map((p) => <ListingCard key={p.id} pkg={p} />)}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-brand-line p-10 text-center text-brand-ink-soft">
            New domestic packages coming soon.
          </div>
        )}
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-7xl px-6 pb-24" data-testid="home-cta-section">
        <div className="relative overflow-hidden rounded-3xl bg-brand-ocean-deep text-white">
          <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-brand-sunset/30 blur-3xl" />
          <div className="relative grid gap-8 p-10 md:p-14 md:grid-cols-[1.4fr,1fr] items-center">
            <div>
              <div className="text-[11px] uppercase tracking-[0.25em] text-brand-sunset-soft mb-3">Talk to a travel agent</div>
              <h3 className="font-display text-3xl md:text-4xl leading-tight">
                Not sure yet? An agent can build the trip around your dates, group, and budget.
              </h3>
            </div>
            <div className="flex flex-col sm:flex-row md:flex-col gap-3">
              <Link
                to="/contact"
                className="inline-flex items-center justify-center rounded-full bg-brand-sunset px-6 py-3 font-semibold text-white hover:bg-brand-sunset/90"
                data-testid="home-cta-contact"
              >
                Contact an agent
              </Link>
              <Link
                to="/packages"
                className="inline-flex items-center justify-center rounded-full bg-white/10 px-6 py-3 font-semibold text-white hover:bg-white/20"
              >
                Browse all packages
              </Link>
            </div>
          </div>
        </div>
      </section>
    </PageShell>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="aspect-[4/3] rounded-2xl bg-brand-mist animate-pulse" />
      ))}
    </div>
  );
}
