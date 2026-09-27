import { useParams, Link } from "react-router-dom";
import PageShell from "@/components/public/PageShell";
import ListingCard from "@/components/public/ListingCard";
import { useDestination } from "@/hooks/public";

export default function DestinationDetailPage() {
  const { slug } = useParams();
  const { data, isLoading, isError } = useDestination(slug);

  if (isLoading) {
    return (
      <PageShell>
        <div className="mx-auto max-w-7xl px-6 py-24 text-center text-brand-ink-soft">
          Loading destination…
        </div>
      </PageShell>
    );
  }
  if (isError || !data) {
    return (
      <PageShell>
        <div className="mx-auto max-w-3xl px-6 py-24 text-center" data-testid="destination-not-found">
          <div className="text-[11px] uppercase tracking-[0.3em] text-brand-ocean mb-3">404</div>
          <h1 className="font-display text-3xl">We couldn't find that destination.</h1>
          <Link to="/destinations" className="mt-6 inline-block text-brand-ocean underline">
            Back to destinations
          </Link>
        </div>
      </PageShell>
    );
  }

  const d = data.destination;
  const packages = data.packages || [];

  return (
    <PageShell heroTransparent>
      <section
        className="relative brand-grain"
        data-testid={`destination-detail-${d.slug}`}
      >
        <div className="absolute inset-0">
          <img
            src={d.hero_image_url || "https://images.unsplash.com/photo-1500835556837-99ac94a94552?q=80&w=1800"}
            alt=""
            className="h-full w-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-brand-ink/60 via-brand-ink/30 to-brand-ink/70" />
        </div>
        <div className="relative mx-auto max-w-7xl px-6 pt-40 pb-24 md:pt-52 md:pb-32">
          <div className="text-[11px] uppercase tracking-[0.3em] text-brand-sunset-soft mb-3">
            {d.scope === "domestic" ? "Philippines" : d.country}
          </div>
          <h1 className="font-display text-5xl md:text-6xl text-white leading-[1.05]">
            {d.name}
          </h1>
          {d.short_description ? (
            <p className="mt-5 text-lg text-white/85 max-w-2xl">{d.short_description}</p>
          ) : null}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-16 md:py-20">
        {d.long_description ? (
          <p className="max-w-3xl text-brand-ink-soft leading-relaxed mb-10">
            {d.long_description}
          </p>
        ) : null}

        <h2 className="font-display text-2xl md:text-3xl text-brand-ink mb-6">
          {packages.length ? "Available packages" : "Packages coming soon"}
        </h2>

        {packages.length ? (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3" data-testid="destination-packages-grid">
            {packages.map((p) => <ListingCard key={p.id} pkg={p} />)}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-brand-line p-10 text-center text-brand-ink-soft">
            Want to travel here? <Link to="/contact" className="text-brand-ocean underline">Contact an agent</Link>
            {" "}for a custom itinerary.
          </div>
        )}
      </section>
    </PageShell>
  );
}
