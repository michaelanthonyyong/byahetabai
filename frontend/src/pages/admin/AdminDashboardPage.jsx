import { Link } from "react-router-dom";
import PortalHeader from "@/components/portal/PortalHeader";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function AdminDashboardPage() {
  const { user } = useAuth();
  return (
    <div className="min-h-screen bg-stone-50">
      <PortalHeader title="Admin Portal" />
      <main className="mx-auto max-w-6xl px-6 py-10 space-y-6" data-testid="admin-dashboard">
        <div>
          <h1 className="text-2xl font-semibold text-stone-900">
            Welcome, {user?.display_name || "admin"}.
          </h1>
          <p className="text-sm text-stone-600 mt-1">
            Manage agents and — in later phases — packages, bookings, approvals.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Agent management</CardTitle>
              <CardDescription>Invite new agents, reset passwords, enable / disable accounts.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild data-testid="admin-goto-agents">
                <Link to="/admin/agents">Open agents</Link>
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Catalog &amp; approvals</CardTitle>
              <CardDescription>Destinations, packages, fund requests and commissions arrive in later phases.</CardDescription>
            </CardHeader>
            <CardContent className="text-xs text-stone-500">Deferred — Phase 3 &amp; later</CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
