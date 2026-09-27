import PageShell from "@/components/public/PageShell";
import { Link } from "react-router-dom";
import { Compass, HeartHandshake, Map } from "lucide-react";

export default function AboutPage() {
  return (
    <PageShell>
      <section className="mx-auto max-w-4xl px-6 py-16 md:py-24" data-testid="about-page">
        <div className="text-[11px] uppercase tracking-[0.3em] text-brand-ocean mb-4">About us</div>
        <h1 className="font-display text-4xl md:text-6xl leading-tight text-brand-ink">
          Local and international travel, made effortless.
        </h1>
        <p className="mt-6 text-lg text-brand-ink-soft leading-relaxed">
          Biyahe'Ta Bai Travel started with a simple idea: getting Filipinos on great trips
          shouldn't feel like paperwork. We work with a curated network of travel agents to
          plan, book, and support every itinerary — from a Cebu long weekend to a two-week
          swing across Japan.
        </p>
      </section>

      <section className="bg-white/60 border-y border-brand-line">
        <div className="mx-auto max-w-6xl px-6 py-16 grid gap-8 md:grid-cols-3">
          {[
            {
              Icon: Compass,
              title: "Curated packages",
              body: "Vetted itineraries for popular routes — no guessing at hotels or transfers.",
            },
            {
              Icon: HeartHandshake,
              title: "Real agents, real conversations",
              body: "Chat with a person who can tailor the trip to your group and budget.",
            },
            {
              Icon: Map,
              title: "Local plus international",
              body: "From island-hopping in the Visayas to charter flights across Asia.",
            },
          ].map(({ Icon, title, body }) => (
            <div key={title} className="rounded-2xl border border-brand-line bg-white p-6">
              <Icon className="text-brand-ocean" />
              <h3 className="font-display text-xl mt-4 text-brand-ink">{title}</h3>
              <p className="mt-2 text-sm text-brand-ink-soft leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-6 py-16 md:py-24 text-center">
        <h2 className="font-display text-3xl md:text-4xl text-brand-ink">
          Ready to plan your next trip?
        </h2>
        <div className="mt-6 flex flex-col sm:flex-row justify-center gap-3">
          <Link
            to="/packages"
            className="inline-flex items-center justify-center rounded-full bg-brand-ocean px-6 py-3 font-semibold text-white hover:bg-brand-ocean-deep"
          >
            Browse packages
          </Link>
          <Link
            to="/contact"
            className="inline-flex items-center justify-center rounded-full border border-brand-ocean px-6 py-3 font-semibold text-brand-ocean hover:bg-brand-mist"
          >
            Contact an agent
          </Link>
        </div>
      </section>
    </PageShell>
  );
}
