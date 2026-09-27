import { Link } from "react-router-dom";

export default function SectionHeader({ eyebrow, title, description, actionHref, actionLabel }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between mb-8 md:mb-10">
      <div className="max-w-xl">
        {eyebrow ? (
          <div className="text-[11px] uppercase tracking-[0.25em] text-brand-ocean mb-3">
            {eyebrow}
          </div>
        ) : null}
        <h2 className="font-display text-3xl md:text-4xl text-brand-ink leading-tight">
          {title}
        </h2>
        {description ? (
          <p className="mt-3 text-brand-ink-soft leading-relaxed">{description}</p>
        ) : null}
      </div>
      {actionHref ? (
        <Link
          to={actionHref}
          className="text-sm font-semibold text-brand-ocean hover:text-brand-ocean-deep border-b border-brand-ocean/30 hover:border-brand-ocean-deep pb-1 self-start"
        >
          {actionLabel || "See all →"}
        </Link>
      ) : null}
    </div>
  );
}
