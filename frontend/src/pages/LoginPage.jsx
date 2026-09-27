import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function LoginPage() {
  const { login, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Redirect already-signed-in visitors away from /login.
  useEffect(() => {
    if (user && user.role) {
      const fallback = user.role === "admin" ? "/admin" : "/agent";
      navigate(location.state?.from?.pathname || fallback, { replace: true });
    }
  }, [user, location.state, navigate]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    const { ok, user: u, error: err } = await login(email, password);
    setBusy(false);
    if (!ok) {
      setError(err);
      return;
    }
    const from = location.state?.from?.pathname;
    const fallback = u.role === "admin" ? "/admin" : "/agent";
    navigate(from || fallback, { replace: true });
  };

  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center px-4">
      <Card className="w-full max-w-md" data-testid="login-card">
        <CardHeader className="space-y-2">
          <div className="text-xs uppercase tracking-widest text-stone-500">Biyahe'Ta Bai Travel</div>
          <CardTitle className="text-2xl">Sign in to the portal</CardTitle>
          <CardDescription>
            Admin &amp; agent access only. Agents must accept their invitation first.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4" data-testid="login-form">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email" type="email" autoComplete="email" required
                value={email} onChange={(e) => setEmail(e.target.value)}
                data-testid="login-email-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password" type="password" autoComplete="current-password" required
                value={password} onChange={(e) => setPassword(e.target.value)}
                data-testid="login-password-input"
              />
            </div>
            {error ? (
              <Alert variant="destructive" data-testid="login-error">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            <Button
              type="submit" className="w-full" disabled={busy}
              data-testid="login-submit-button"
            >
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
