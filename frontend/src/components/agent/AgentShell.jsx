import { Link, NavLink } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { PrivacyToggle } from "@/components/agent/PrivacyToggle";
import { NotificationBell } from "@/components/agent/NotificationBell";
import { LayoutDashboard, Compass, Wallet, BookText, UserRound, LogOut, Users, ReceiptText } from "lucide-react";

const NAV = [
  { to: "/agent", label: "Dashboard", icon: LayoutDashboard, end: true, id: "dashboard" },
  { to: "/agent/catalog", label: "Catalog", icon: Compass, id: "catalog" },
  { to: "/agent/bookings", label: "Bookings", icon: ReceiptText, id: "bookings" },
  { to: "/agent/customers", label: "Customers", icon: Users, id: "customers" },
  { to: "/agent/top-ups", label: "Top-ups", icon: Wallet, id: "top-ups" },
  { to: "/agent/ledger", label: "Ledger", icon: BookText, id: "ledger" },
  { to: "/agent/profile", label: "Profile", icon: UserRound, id: "profile" },
];

const navCls = ({ isActive }) =>
  [
    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
    isActive ? "bg-teal-800 text-white" : "text-stone-600 hover:bg-stone-100 hover:text-stone-900",
  ].join(" ");

const Sidebar = ({ user, logout }) => (
  <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-stone-200 bg-white">
    <div className="px-6 py-5 border-b border-stone-200">
      <Link to="/agent" className="block">
        <div className="text-[10px] uppercase tracking-[0.25em] text-teal-700">Agent portal</div>
        <div className="font-display text-lg text-stone-900 mt-1">Biyahe'Ta Bai</div>
      </Link>
    </div>
    <nav className="flex-1 px-3 py-4 space-y-1">
      {NAV.map(({ to, label, icon: Icon, end, id }) => (
        <NavLink key={to} to={to} end={end} className={navCls} data-testid={`agent-nav-${id}`}>
          <Icon size={16} /> <span>{label}</span>
        </NavLink>
      ))}
    </nav>
    <div className="border-t border-stone-200 px-3 py-4">
      <div className="px-3 pb-3 text-xs text-stone-500">
        <div className="truncate font-medium text-stone-700" data-testid="agent-current-user">
          {user?.display_name || user?.email}
        </div>
        <div className="uppercase tracking-widest text-[10px]">Travel agent</div>
      </div>
      <button
        onClick={logout}
        data-testid="agent-logout-button"
        className="w-full flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-stone-600 hover:bg-stone-100 hover:text-stone-900"
      >
        <LogOut size={16} /> Sign out
      </button>
    </div>
  </aside>
);

const MobileHeader = ({ logout }) => (
  <header className="border-b border-stone-200 bg-white lg:hidden">
    <div className="flex items-center justify-between px-4 py-3">
      <Link to="/agent" className="font-display text-base">Biyahe'Ta Bai · Agent</Link>
      <div className="flex items-center gap-2">
        <NotificationBell testid="notification-bell-mobile" />
        <PrivacyToggle compact testid="privacy-toggle-mobile" />
        <button onClick={logout} className="text-xs text-stone-600" data-testid="agent-logout-button-mobile">
          Sign out
        </button>
      </div>
    </div>
    <div className="flex overflow-x-auto border-t border-stone-200 px-2">
      {NAV.map(({ to, label, end, id }) => (
        <NavLink
          key={to} to={to} end={end} data-testid={`agent-mobile-nav-${id}`}
          className={({ isActive }) =>
            ["shrink-0 px-3 py-3 text-sm border-b-2",
              isActive ? "border-teal-700 text-stone-900 font-medium" : "border-transparent text-stone-500"].join(" ")
          }
        >{label}</NavLink>
      ))}
    </div>
  </header>
);

export default function AgentShell({ title, subtitle, actions, children }) {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-stone-50 text-stone-900">
      <div className="flex min-h-screen">
        <Sidebar user={user} logout={logout} />
        <div className="flex-1 min-w-0 flex flex-col">
          <MobileHeader logout={logout} />
          <div className="border-b border-stone-200 bg-white">
            <div className="px-4 sm:px-6 lg:px-10 py-6 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
              <div>
                {subtitle ? (
                  <div className="text-[11px] uppercase tracking-[0.25em] text-teal-700 mb-1">{subtitle}</div>
                ) : null}
                <h1 className="font-display text-2xl sm:text-3xl text-stone-900" data-testid="agent-page-title">{title}</h1>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {actions}
                <div className="hidden lg:flex items-center gap-2"><NotificationBell /><PrivacyToggle /></div>
              </div>
            </div>
          </div>
          <main className="flex-1 px-4 sm:px-6 lg:px-10 py-8">{children}</main>
        </div>
      </div>
    </div>
  );
}
