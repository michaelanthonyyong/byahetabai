import "@/App.css";
import { BrowserRouter, Routes, Route, Link, Navigate } from "react-router-dom";
import { Toaster } from "sonner";

import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import RequireAuth from "@/components/auth/RequireAuth";
import LoginPage from "@/pages/LoginPage";
import SetPasswordPage from "@/pages/SetPasswordPage";
import ForbiddenPage from "@/pages/ForbiddenPage";
import AgentDashboardPage from "@/pages/agent/AgentDashboardPage";
import AdminDashboardPage from "@/pages/admin/AdminDashboardPage";
import AdminAgentsPage from "@/pages/admin/AdminAgentsPage";
import { Button } from "@/components/ui/button";

/**
 * Temporary landing page while the public marketing site (Phase 3) is not
 * yet built.  Sends the visitor to /login or their portal.
 */
function Landing() {
  const { user } = useAuth();
  const target =
    user && user.role === "admin" ? "/admin" :
    user && user.role === "agent" ? "/agent" : null;
  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center px-4">
      <div className="max-w-xl text-center space-y-6" data-testid="landing-page">
        <div className="text-xs uppercase tracking-widest text-stone-500">Biyahe'Ta Bai Travel</div>
        <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight text-stone-900">
          Go. Explore. Discover.
        </h1>
        <p className="text-sm text-stone-600">
          The public website is under construction. Portal access below.
        </p>
        <div className="flex justify-center gap-3">
          {target ? (
            <Button asChild data-testid="landing-portal-button">
              <Link to={target}>Go to my portal</Link>
            </Button>
          ) : (
            <Button asChild data-testid="landing-login-button">
              <Link to="/login">Sign in</Link>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors closeButton />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/accept-invite" element={<SetPasswordPage mode="invite" />} />
          <Route path="/reset-password" element={<SetPasswordPage mode="reset" />} />
          <Route path="/forbidden" element={<ForbiddenPage />} />

          {/* Agent portal */}
          <Route
            path="/agent"
            element={
              <RequireAuth roles={["agent"]}>
                <AgentDashboardPage />
              </RequireAuth>
            }
          />

          {/* Admin portal */}
          <Route
            path="/admin"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminDashboardPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/agents"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminAgentsPage />
              </RequireAuth>
            }
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
