import { Link } from "react-router-dom";
import { formatPHP } from "@/lib/money";
import { Users, Clock } from "lucide-react";

const FALLBACK_IMG =
  "https://images.unsplash.com/photo-1500835556837-99ac94a94552?q=80&w=1200";

export default function ListingCard({ pkg }) {
  const price = pkg.guest_price ? formatPHP(pkg.guest_price) : null;
  const loc =
    pkg.destination
      ? `${pkg.destination.name}${pkg.destination.country && pkg.destination.country !== pkg.destination.name ? `, ${pkg.destination.country}` : ""}`
      : "";
  return (
    <Link
      to={`/packages/${pkg.slug}`}
      data-testid={`listing-card-${pkg.slug}`}
      className="group flex flex-col overflow-hidden rounded-2xl bg-white border border-brand-line hover:border-brand-ocean/30 hover:shadow-[0_10px_40px_-20px_rgba(14,76,110,0.35)] transition-all"
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-brand-mist">
        <img
          src={pkg.cover_image_url || FALLBACK_IMG}
          alt={pkg.title}
          className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
          loading="lazy"
        />
        <div className="absolute left-3 top-3 rounded-full bg-white/95 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-brand-ocean">
          Tour
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-5">
        <h3 className="font-display text-lg leading-snug text-brand-ink line-clamp-2">
          {pkg.title}
        </h3>
        {loc ? <div className="text-xs text-brand-ink-soft">{loc}</div> : null}
        <div className="mt-auto flex items-end justify-between pt-3 border-t border-brand-line">
          <div>
            {price ? (
              <>
                <div className="text-[10px] uppercase tracking-widest text-brand-ink-soft">from</div>
                <div className="font-display text-xl text-brand-ink">{price}</div>
              </>
            ) : (
              <div className="text-xs text-brand-ink-soft">Enquire for pricing</div>
            )}
          </div>
          <div className="flex flex-col items-end gap-1 text-[11px] text-brand-ink-soft">
            {pkg.duration_days ? (
              <span className="inline-flex items-center gap-1">
                <Clock size={12} /> {pkg.duration_days}D{pkg.duration_nights ? `${pkg.duration_nights}N` : ""}
              </span>
            ) : null}
            {pkg.max_pax ? (
              <span className="inline-flex items-center gap-1">
                <Users size={12} /> up to {pkg.max_pax} pax
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </Link>
  );
}
