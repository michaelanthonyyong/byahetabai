import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";

/**
 * Compact portal header shared by admin and agent post-login pages.
 * Not the public marketing header — that's Phase 3.
 */
export default function PortalHeader({ title }) {
  const { user, logout } = useAuth();
  return (
    <header className="border-b border-stone-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-6">
          <Link to="/" className="text-sm font-semibold tracking-wide">
            Biyahe'Ta Bai Travel
          </Link>
          {title ? (
            <span className="text-xs uppercase tracking-widest text-stone-500">{title}</span>
          ) : null}
        </div>
        <div className="flex items-center gap-4">
          {user && user.email ? (
            <span
              className="text-xs text-stone-600"
              data-testid="portal-current-user"
            >
              {user.display_name || user.email} · <span className="uppercase">{user.role}</span>
            </span>
          ) : null}
          <Button
            variant="outline" size="sm" onClick={logout}
            data-testid="portal-logout-button"
          >
            Sign out
          </Button>
        </div>
      </div>
    </header>
  );
}
