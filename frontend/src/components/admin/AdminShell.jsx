import { Link, NavLink } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import {
  LayoutDashboard, Users, Package, ReceiptText, ArrowLeftRight,
  ClipboardList, Settings, LogOut, MapPin, Inbox, ShieldCheck,
} from "lucide-react";

const NAV = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/admin/agents", label: "Agents", icon: Users },
  { to: "/admin/packages", label: "Packages", icon: Package },
  { to: "/admin/destinations", label: "Destinations", icon: MapPin },
  { to: "/admin/bookings", label: "Bookings", icon: ReceiptText },
  { to: "/admin/fund-requests", label: "Fund Requests", icon: ClipboardList },
  { to: "/admin/transactions", label: "Transactions", icon: ArrowLeftRight },
  { to: "/admin/contacts", label: "Contact Messages", icon: Inbox },
  { to: "/admin/audit-logs", label: "Audit Log", icon: ShieldCheck },
  { to: "/admin/settings", label: "Settings", icon: Settings },
];

export default function AdminShell({ title, subtitle, actions, children }) {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-stone-50 text-stone-900">
      <div className="flex min-h-screen">
        {/* Sidebar */}
        <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-stone-200 bg-white">
          <div className="px-6 py-5 border-b border-stone-200">
            <Link to="/admin" className="block">
              <div className="text-[10px] uppercase tracking-[0.25em] text-stone-500">Admin</div>
              <div className="font-semibold text-stone-900 mt-1">Biyahe'Ta Bai</div>
            </Link>
          </div>
          <nav className="flex-1 px-3 py-4 space-y-1">
            {NAV.map(({ to, label, icon: Icon, soon, end }) => (
              <NavLink
                key={to} to={to} end={end}
                data-testid={`admin-nav-${label.toLowerCase()}`}
                className={({ isActive }) =>
                  [
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    soon
                      ? "text-stone-400 cursor-not-allowed"
                      : isActive
                        ? "bg-stone-900 text-white"
                        : "text-stone-600 hover:bg-stone-100 hover:text-stone-900",
                  ].join(" ")
                }
                onClick={(e) => { if (soon) e.preventDefault(); }}
              >
                <Icon size={16} />
                <span>{label}</span>
                {soon ? <span className="ml-auto text-[10px] uppercase tracking-widest text-stone-400">Soon</span> : null}
              </NavLink>
            ))}
          </nav>
          <div className="border-t border-stone-200 px-3 py-4">
            <div className="px-3 pb-3 text-xs text-stone-500">
              <div className="truncate font-medium text-stone-700" data-testid="admin-current-user">
                {user?.display_name || user?.email}
              </div>
              <div className="uppercase tracking-widest text-[10px]">Master admin</div>
            </div>
            <button
              onClick={logout}
              data-testid="admin-logout-button"
              className="w-full flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-stone-600 hover:bg-stone-100 hover:text-stone-900"
            >
              <LogOut size={16} /> Sign out
            </button>
          </div>
        </aside>

        {/* Main */}
        <div className="flex-1 min-w-0 flex flex-col">
          <header className="border-b border-stone-200 bg-white lg:hidden">
            <div className="flex items-center justify-between px-6 py-4">
              <Link to="/admin" className="font-semibold">Biyahe'Ta Bai · Admin</Link>
              <button onClick={logout} className="text-xs text-stone-600" data-testid="admin-logout-button-mobile">
                Sign out
              </button>
            </div>
            <div className="flex overflow-x-auto border-t border-stone-200 px-4">
              {NAV.filter((n) => !n.soon).map(({ to, label, end }) => (
                <NavLink
                  key={to} to={to} end={end}
                  className={({ isActive }) =>
                    ["shrink-0 px-3 py-3 text-sm border-b-2",
                     isActive ? "border-stone-900 text-stone-900 font-medium" : "border-transparent text-stone-500"
                    ].join(" ")
                  }
                >{label}</NavLink>
              ))}
            </div>
          </header>

          <div className="border-b border-stone-200 bg-white">
            <div className="px-6 lg:px-10 py-6 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
              <div>
                {subtitle ? (
                  <div className="text-[11px] uppercase tracking-[0.25em] text-stone-500 mb-1">{subtitle}</div>
                ) : null}
                <h1 className="text-2xl font-semibold text-stone-900" data-testid="admin-page-title">{title}</h1>
              </div>
              {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
            </div>
          </div>

          <main className="flex-1 px-6 lg:px-10 py-8">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
