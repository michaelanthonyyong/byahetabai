import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";

import { AuthProvider } from "@/contexts/AuthContext";
import RequireAuth from "@/components/auth/RequireAuth";
import LoginPage from "@/pages/LoginPage";
import SetPasswordPage from "@/pages/SetPasswordPage";
import ForbiddenPage from "@/pages/ForbiddenPage";
import AgentDashboardPage from "@/pages/agent/AgentDashboardPage";
import AdminDashboardPage from "@/pages/admin/AdminDashboardPage";
import AdminAgentsPage from "@/pages/admin/AdminAgentsPage";
import AdminAgentDetailPage from "@/pages/admin/AdminAgentDetailPage";

// Public marketing pages
import HomePage from "@/pages/public/HomePage";
import AboutPage from "@/pages/public/AboutPage";
import DestinationsPage from "@/pages/public/DestinationsPage";
import DestinationDetailPage from "@/pages/public/DestinationDetailPage";
import PackagesPage from "@/pages/public/PackagesPage";
import PackageDetailPage from "@/pages/public/PackageDetailPage";
import ContactPage from "@/pages/public/ContactPage";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors closeButton />
        <Routes>
          {/* Public marketing site */}
          <Route path="/" element={<HomePage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/destinations" element={<DestinationsPage />} />
          <Route path="/destinations/:slug" element={<DestinationDetailPage />} />
          <Route path="/packages" element={<PackagesPage />} />
          <Route path="/packages/:slug" element={<PackageDetailPage />} />
          <Route path="/contact" element={<ContactPage />} />

          {/* Auth */}
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
          <Route
            path="/admin/agents/:id"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminAgentDetailPage />
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
