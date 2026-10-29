import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";

import { AuthProvider } from "@/contexts/AuthContext";
import RequireAuth from "@/components/auth/RequireAuth";
import LoginPage from "@/pages/LoginPage";
import SetPasswordPage from "@/pages/SetPasswordPage";
import ForbiddenPage from "@/pages/ForbiddenPage";
import AgentDashboardPage from "@/pages/agent/AgentDashboardPage";
import AgentCatalogPage from "@/pages/agent/AgentCatalogPage";
import AgentPackageDetailPage from "@/pages/agent/AgentPackageDetailPage";
import AgentFundRequestsPage from "@/pages/agent/AgentFundRequestsPage";
import AgentLedgerPage from "@/pages/agent/AgentLedgerPage";
import AgentProfilePage from "@/pages/agent/AgentProfilePage";
import { PrivacyProvider } from "@/contexts/PrivacyContext";
import AdminDashboardPage from "@/pages/admin/AdminDashboardPage";
import AdminAgentsPage from "@/pages/admin/AdminAgentsPage";
import AdminAgentDetailPage from "@/pages/admin/AdminAgentDetailPage";
import AdminBookingsPage from "@/pages/admin/AdminBookingsPage";
import AdminBookingDetailPage from "@/pages/admin/AdminBookingDetailPage";
import AdminPackagesPage from "@/pages/admin/AdminPackagesPage";
import AdminPackageEditorPage from "@/pages/admin/AdminPackageEditorPage";
import AdminDestinationsPage from "@/pages/admin/AdminDestinationsPage";
import AdminFundRequestsPage from "@/pages/admin/AdminFundRequestsPage";
import AdminTransactionsPage from "@/pages/admin/AdminTransactionsPage";
import AdminContactsPage from "@/pages/admin/AdminContactsPage";
import AdminSettingsPage from "@/pages/admin/AdminSettingsPage";
import AdminAuditLogsPage from "@/pages/admin/AdminAuditLogsPage";

// Public marketing pages
import HomePage from "@/pages/public/HomePage";
import AboutPage from "@/pages/public/AboutPage";
import DestinationsPage from "@/pages/public/DestinationsPage";
import DestinationDetailPage from "@/pages/public/DestinationDetailPage";
import PackagesPage from "@/pages/public/PackagesPage";
import PackageDetailPage from "@/pages/public/PackageDetailPage";
import ContactPage from "@/pages/public/ContactPage";

const agentRoute = (el) => (
  <RequireAuth roles={["agent"]}><PrivacyProvider>{el}</PrivacyProvider></RequireAuth>
);

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
          <Route path="/agent" element={agentRoute(<AgentDashboardPage />)} />
          <Route path="/agent/catalog" element={agentRoute(<AgentCatalogPage />)} />
          <Route path="/agent/catalog/:id" element={agentRoute(<AgentPackageDetailPage />)} />
          <Route path="/agent/top-ups" element={agentRoute(<AgentFundRequestsPage />)} />
          <Route path="/agent/ledger" element={agentRoute(<AgentLedgerPage />)} />
          <Route path="/agent/profile" element={agentRoute(<AgentProfilePage />)} />

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
          <Route
            path="/admin/bookings"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminBookingsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/bookings/:id"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminBookingDetailPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/packages"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminPackagesPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/packages/:id"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminPackageEditorPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/destinations"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminDestinationsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/fund-requests"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminFundRequestsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/transactions"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminTransactionsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/contacts"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminContactsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/settings"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminSettingsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/audit-logs"
            element={
              <RequireAuth roles={["admin"]}>
                <AdminAuditLogsPage />
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
