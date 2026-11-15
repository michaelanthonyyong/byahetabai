import { Link, useParams } from "react-router-dom";
import { useState } from "react";
import PageShell from "@/components/public/PageShell";
import { usePackage } from "@/hooks/public";
import { formatPHP } from "@/lib/money";
import { Clock, Users, MapPin, Check, X } from "lucide-react";

export default function PackageDetailPage() {
  const { slug } = useParams();
  const { data: pkg, isLoading, isError } = usePackage(slug);
  const [activeIdx, setActiveIdx] = useState(0);

  if (isLoading) {
    return (
      <PageShell>
        <div className="mx-auto max-w-7xl px-6 py-24 text-center text-brand-ink-soft">
          Loading package…
        </div>
      </PageShell>
    );
  }
  if (isError || !pkg) {
    return (
      <PageShell>
        <div className="mx-auto max-w-3xl px-6 py-24 text-center" data-testid="package-not-found">
          <div className="text-[11px] uppercase tracking-[0.3em] text-brand-ocean mb-3">404</div>
          <h1 className="font-display text-3xl">We couldn't find that package.</h1>
          <Link to="/packages" className="mt-6 inline-block text-brand-ocean underline">
            Back to packages
          </Link>
        </div>
      </PageShell>
    );
  }

  const images = pkg.images && pkg.images.length ? pkg.images : (pkg.cover_image_url ? [{ id: "c", url: pkg.cover_image_url }] : []);
  const active = images[activeIdx] || images[0];

  const contactHref = `/contact?package=${encodeURIComponent(pkg.slug)}`;

  return (
    <PageShell>
      <div className="mx-auto max-w-7xl px-6 py-10 md:py-14" data-testid={`package-detail-${pkg.slug}`}>
        {/* Breadcrumb */}
        <nav className="text-xs text-brand-ink-soft flex gap-2 mb-6" aria-label="Breadcrumb">
          <Link to="/" className="hover:text-brand-ocean">Home</Link><span>/</span>
          <Link to="/packages" className="hover:text-brand-ocean">Tours</Link><span>/</span>
          {pkg.destination ? (
            <>
              <Link to={`/destinations/${pkg.destination.slug}`} className="hover:text-brand-ocean">
                {pkg.destination.name}
              </Link>
              <span>/</span>
            </>
          ) : null}
          <span className="text-brand-ink truncate max-w-[240px]">{pkg.title}</span>
        </nav>

        <div className="grid gap-10 lg:grid-cols-[1.4fr,1fr]">
          {/* Left column */}
          <div>
            {/* Gallery */}
            <div className="rounded-3xl overflow-hidden bg-brand-mist aspect-[4/3] mb-4" data-testid="package-hero-image">
              {active ? (
                <img src={active.url} alt={active.alt || pkg.title} className="h-full w-full object-cover" />
              ) : null}
            </div>
            {images.length > 1 ? (
              <div className="grid grid-cols-5 gap-2" data-testid="package-thumbnails">
                {images.slice(0, 5).map((img, i) => (
                  <button
                    key={img.id || i}
                    onClick={() => setActiveIdx(i)}
                    className={[
                      "aspect-[4/3] overflow-hidden rounded-xl border-2 transition-colors",
                      i === activeIdx ? "border-brand-ocean" : "border-transparent hover:border-brand-line",
                    ].join(" ")}
                  >
                    <img src={img.url} alt="" className="h-full w-full object-cover" loading="lazy" />
                  </button>
                ))}
              </div>
            ) : null}

            <div className="mt-10">
              <div className="text-[11px] uppercase tracking-[0.3em] text-brand-ocean mb-2">
                Tour package
              </div>
              <h1 className="font-display text-4xl md:text-5xl leading-tight text-brand-ink">
                {pkg.title}
              </h1>

              <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm text-brand-ink-soft">
                {pkg.destination ? (
                  <span className="inline-flex items-center gap-1.5">
                    <MapPin size={14} className="text-brand-ocean" />
                    {pkg.destination.name}{pkg.destination.country && pkg.destination.country !== pkg.destination.name ? `, ${pkg.destination.country}` : ""}
                  </span>
                ) : null}
                {pkg.duration_days ? (
                  <span className="inline-flex items-center gap-1.5">
                    <Clock size={14} className="text-brand-ocean" />
                    {pkg.duration_days} day{pkg.duration_days > 1 ? "s" : ""}
                    {pkg.duration_nights ? `, ${pkg.duration_nights} night${pkg.duration_nights > 1 ? "s" : ""}` : ""}
                  </span>
                ) : null}
                {pkg.max_pax ? (
                  <span className="inline-flex items-center gap-1.5">
                    <Users size={14} className="text-brand-ocean" />
                    up to {pkg.max_pax} pax
                  </span>
                ) : null}
              </div>

              {pkg.summary ? (
                <p className="mt-6 text-lg leading-relaxed text-brand-ink-soft">{pkg.summary}</p>
              ) : null}
            </div>

            {pkg.highlights ? (
              <section className="mt-10">
                <h2 className="font-display text-2xl text-brand-ink mb-3">Highlights</h2>
                <p className="text-brand-ink-soft leading-relaxed whitespace-pre-line">{pkg.highlights}</p>
              </section>
            ) : null}

            {pkg.itinerary ? (
              <section className="mt-10">
                <h2 className="font-display text-2xl text-brand-ink mb-3">Itinerary</h2>
                <p className="text-brand-ink-soft leading-relaxed whitespace-pre-line">{pkg.itinerary}</p>
              </section>
            ) : null}

            <div className="mt-10 grid gap-8 md:grid-cols-2">
              {pkg.inclusions?.length ? (
                <section data-testid="package-inclusions">
                  <h2 className="font-display text-xl text-brand-ink mb-3">Inclusions</h2>
                  <ul className="space-y-2">
                    {pkg.inclusions.map((it) => (
                      <li key={it.id} className="flex items-start gap-2 text-sm text-brand-ink-soft">
                        <Check size={16} className="mt-0.5 shrink-0 text-brand-ocean" />
                        <span>{it.text}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              {pkg.exclusions?.length ? (
                <section data-testid="package-exclusions">
                  <h2 className="font-display text-xl text-brand-ink mb-3">Exclusions</h2>
                  <ul className="space-y-2">
                    {pkg.exclusions.map((it) => (
                      <li key={it.id} className="flex items-start gap-2 text-sm text-brand-ink-soft">
                        <X size={16} className="mt-0.5 shrink-0 text-brand-sunset" />
                        <span>{it.text}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </div>
          </div>

          {/* Right column — booking sidebar */}
          <aside className="lg:sticky lg:top-28 self-start">
            <div className="rounded-3xl border border-brand-line bg-white p-6 md:p-7 shadow-[0_10px_50px_-30px_rgba(14,76,110,0.35)]" data-testid="package-cta-card">
              {pkg.guest_price ? (
                <>
                  <div className="text-[11px] uppercase tracking-widest text-brand-ink-soft">From</div>
                  <div className="font-display text-4xl text-brand-ink" data-testid="package-price">
                    {formatPHP(pkg.guest_price)}
                  </div>
                  <div className="text-xs text-brand-ink-soft mt-1">per person</div>
                </>
              ) : (
                <div className="text-brand-ink-soft">Contact us for pricing</div>
              )}

              <div className="mt-6 space-y-3">
                <Link
                  to={contactHref}
                  className="block w-full rounded-full bg-brand-sunset text-white text-center font-semibold py-3 hover:bg-brand-sunset/90 transition-colors"
                  data-testid="package-contact-agent-cta"
                >
                  Contact an agent
                </Link>
                <Link
                  to="/packages"
                  className="block w-full rounded-full border border-brand-ocean text-brand-ocean text-center font-semibold py-3 hover:bg-brand-mist transition-colors"
                >
                  Browse more packages
                </Link>
              </div>

              <div className="mt-6 text-xs text-brand-ink-soft leading-relaxed">
                Book, pay, and confirm through an eNaviga travel agent. We'll match you with someone
                who knows this route.
              </div>
            </div>
          </aside>
        </div>
      </div>
    </PageShell>
  );
}
