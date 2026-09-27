import { Link } from "react-router-dom";

const FALLBACK =
  "https://images.unsplash.com/photo-1500835556837-99ac94a94552?q=80&w=1200";

export default function DestinationTile({ destination, size = "md" }) {
  const heights = { sm: "h-40", md: "h-56 md:h-64", lg: "h-72 md:h-96" };
  return (
    <Link
      to={`/destinations/${destination.slug}`}
      data-testid={`destination-tile-${destination.slug}`}
      className={`group relative block overflow-hidden rounded-2xl ${heights[size]} bg-brand-ink`}
    >
      <img
        src={destination.hero_image_url || FALLBACK}
        alt={destination.name}
        className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
        loading="lazy"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-brand-ink/80 via-brand-ink/10 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 p-4 md:p-5">
        <div className="text-[10px] uppercase tracking-[0.2em] text-brand-sunset-soft">
          {destination.scope === "domestic" ? "Philippines" : destination.country}
        </div>
        <div className="font-display text-xl md:text-2xl text-white leading-tight">
          {destination.name}
        </div>
      </div>
    </Link>
  );
}
