import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api } from "@/lib/api";
import { formatPHP, humanAction, timeAgo } from "@/lib/admin";
import { Card, CardContent, CardHeader, CardDescription, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Users, UserPlus, Wallet, Receipt, Package, MapPin, Inbox, CircleDollarSign } from "lucide-react";

function KpiCard({ icon: Icon, label, value, sub, tone = "default", testid }) {
  const tones = {
    default: "bg-white border-stone-200",
    ocean: "bg-stone-900 text-white border-stone-900",
    warn: "bg-amber-50 border-amber-200",
  };
  return (
    <Card className={tones[tone]} data-testid={testid}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardDescription className={tone === "ocean" ? "text-white/60" : ""}>{label}</CardDescription>
          <Icon size={18} className={tone === "ocean" ? "text-white/60" : "text-stone-400"} />
        </div>
        <CardTitle className={"text-3xl font-semibold " + (tone === "ocean" ? "text-white" : "text-stone-900")}>
          {value}
        </CardTitle>
      </CardHeader>
      {sub ? (
        <CardContent className={"text-xs " + (tone === "ocean" ? "text-white/70" : "text-stone-500")}>
          {sub}
        </CardContent>
      ) : null}
    </Card>
  );
}

export default function AdminDashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin-dashboard"],
    queryFn: () => api.get("/admin/dashboard").then((r) => r.data),
    refetchOnMount: "always",
  });

  return (
    <AdminShell
      subtitle="Overview"
      title="Dashboard"
      actions={
        <Button asChild data-testid="admin-dashboard-invite-cta">
          <Link to="/admin/agents"><UserPlus size={16} className="mr-1.5" />Manage agents</Link>
        </Button>
      }
    >
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 rounded-lg bg-stone-100 animate-pulse" />
          ))}
        </div>
      ) : isError || !data ? (
        <div className="text-sm text-stone-600">Failed to load dashboard.</div>
      ) : (
        <div className="space-y-8" data-testid="admin-dashboard-content">
          {/* KPIs */}
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              icon={Users} label="Agents"
              value={data.agent_counts.total}
              sub={`${data.agent_counts.active} active · ${data.agent_counts.invited} invited · ${data.agent_counts.disabled} disabled`}
              testid="kpi-agents"
            />
            <KpiCard
              icon={Wallet} label="Total booking balance"
              value={formatPHP(data.balances.booking_total)}
              sub="System liability across all agents"
              tone="ocean"
              testid="kpi-booking-balance"
            />
            <KpiCard
              icon={CircleDollarSign} label="Total commission balance"
              value={formatPHP(data.balances.commission_total)}
              sub="Accrued, not yet withdrawn"
              testid="kpi-commission-balance"
            />
            <Link to="/admin/fund-requests?status=pending" className="block group">
              <KpiCard
                icon={Inbox} label="Pending approvals"
                value={data.workflow.pending_fund_requests + data.workflow.pending_withdrawals}
                sub={`${data.workflow.pending_fund_requests} fund · ${data.workflow.pending_withdrawals} withdrawal`}
                tone={data.workflow.pending_fund_requests + data.workflow.pending_withdrawals > 0 ? "warn" : "default"}
                testid="kpi-pending-approvals"
              />
            </Link>
          </section>

          {/* Secondary metrics */}
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard icon={Package} label="Published packages" value={data.catalog.packages_published} sub={`${data.catalog.packages_draft} draft`} testid="kpi-packages" />
            <KpiCard icon={MapPin} label="Destinations" value={data.catalog.destinations_active} testid="kpi-destinations" />
            <KpiCard icon={Receipt} label="Bookings so far" value={data.workflow.total_bookings} testid="kpi-bookings" />
            <Link to="/admin/contacts?status=new" className="block">
              <KpiCard icon={Inbox} label="New contact messages" value={data.workflow.new_contact_messages} testid="kpi-contacts" />
            </Link>
          </section>

          {/* Recent activity */}
          <section>
            <Card>
              <CardHeader>
                <CardTitle>Recent activity</CardTitle>
                <CardDescription>Latest 10 audit log entries</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                {(data.recent_audit || []).length === 0 ? (
                  <div className="p-6 text-sm text-stone-500">No activity yet.</div>
                ) : (
                  <ul className="divide-y divide-stone-100" data-testid="admin-recent-activity">
                    {data.recent_audit.map((e) => (
                      <li key={e.id} className="flex items-start justify-between gap-4 px-6 py-3">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-stone-900">{humanAction(e.action)}</div>
                          <div className="text-xs text-stone-500 truncate">
                            {e.target_type} · {e.target_id?.slice(0, 8)}
                          </div>
                        </div>
                        <Badge variant="outline" className="whitespace-nowrap text-[10px] shrink-0">
                          {timeAgo(e.created_at)}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </section>
        </div>
      )}
    </AdminShell>
  );
}
