import PageShell from "@/components/public/PageShell";
import SectionHeader from "@/components/public/SectionHeader";
import DestinationTile from "@/components/public/DestinationTile";
import { useDestinations } from "@/hooks/public";

export default function DestinationsPage() {
  const { data: destinations, isLoading } = useDestinations();
  const domestic = (destinations || []).filter((d) => d.scope === "domestic");
  const international = (destinations || []).filter((d) => d.scope === "international");
  return (
    <PageShell>
      <section className="mx-auto max-w-7xl px-6 py-14 md:py-20" data-testid="destinations-page">
        <SectionHeader
          eyebrow="Destinations"
          title="Where would you like to travel?"
          description="Popular getaways across the Philippines and around Asia."
        />

        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-56 rounded-2xl bg-brand-mist animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="space-y-16">
            {international.length ? (
              <div>
                <h3 className="font-display text-2xl text-brand-ink mb-4">International</h3>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {international.map((d) => <DestinationTile key={d.id} destination={d} size="lg" />)}
                </div>
              </div>
            ) : null}
            {domestic.length ? (
              <div>
                <h3 className="font-display text-2xl text-brand-ink mb-4">Philippines</h3>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {domestic.map((d) => <DestinationTile key={d.id} destination={d} size="lg" />)}
                </div>
              </div>
            ) : null}
            {!international.length && !domestic.length ? (
              <div className="rounded-2xl border border-dashed border-brand-line p-10 text-center text-brand-ink-soft">
                No destinations available yet.
              </div>
            ) : null}
          </div>
        )}
      </section>
    </PageShell>
  );
}
