import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Blocks the child route until the user is authenticated.
 * Accepts an optional `roles` array; if set, also enforces role membership.
 */
export default function RequireAuth({ children, roles }) {
  const { user } = useAuth();
  const location = useLocation();

  if (user === null) {
    return (
      <div
        data-testid="auth-loading"
        className="flex min-h-screen items-center justify-center text-sm text-muted-foreground"
      >
        Checking session…
      </div>
    );
  }
  if (user === false) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/forbidden" replace />;
  }
  return children;
}
