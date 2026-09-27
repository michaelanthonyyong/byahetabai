import PortalHeader from "@/components/portal/PortalHeader";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export default function AgentDashboardPage() {
  const { user } = useAuth();
  return (
    <div className="min-h-screen bg-stone-50">
      <PortalHeader title="Agent Portal" />
      <main className="mx-auto max-w-6xl px-6 py-10 space-y-6" data-testid="agent-dashboard">
        <div>
          <h1 className="text-2xl font-semibold text-stone-900">
            Welcome back, {user?.display_name || "agent"}.
          </h1>
          <p className="text-sm text-stone-600 mt-1">
            This is your placeholder dashboard. Bookings, balances and commissions arrive in later phases.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardDescription>Booking balance</CardDescription>
              <CardTitle className="text-3xl">₱ 0.00</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-stone-500">Deferred — Phase 5</CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>Commission balance</CardDescription>
              <CardTitle className="text-3xl">₱ 0.00</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-stone-500">Deferred — Phase 7</CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>Active bookings</CardDescription>
              <CardTitle className="text-3xl">—</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-stone-500">Deferred — Phase 6</CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
