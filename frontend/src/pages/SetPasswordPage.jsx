import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";

import BrandLogo from "@/components/BrandLogo";
/**
 * Shared page for accepting an admin invitation and consuming a
 * password-reset token.  Mode is derived from the current pathname
 * (`/accept-invite` vs `/reset-password`) so the copy is contextual.
 */
export default function SetPasswordPage({ mode }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) setError("Missing token in URL.");
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) return setError("Password must be at least 8 characters.");
    if (password !== confirm) return setError("Passwords do not match.");
    setBusy(true);
    try {
      const endpoint = mode === "invite" ? "/auth/accept-invite" : "/auth/reset-password";
      await api.post(endpoint, { token, new_password: password });
      setDone(true);
      setTimeout(() => navigate("/login", { replace: true }), 1500);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const title = mode === "invite" ? "Set your password" : "Choose a new password";
  const blurb =
    mode === "invite"
      ? "Welcome to eNaviga. Set a password to activate your agent account."
      : "Your admin issued a password reset. Choose a new one to continue.";

  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center px-4">
      <Card className="w-full max-w-md" data-testid="set-password-card">
        <CardHeader className="space-y-2">
          <BrandLogo className="h-12" testid="set-password-brand-logo" />
          <CardTitle className="text-2xl">{title}</CardTitle>
          <CardDescription>{blurb}</CardDescription>
        </CardHeader>
        <CardContent>
          {done ? (
            <Alert data-testid="set-password-success">
              <AlertDescription>Password saved. Redirecting to sign-in…</AlertDescription>
            </Alert>
          ) : (
            <form onSubmit={submit} className="space-y-4" data-testid="set-password-form">
              <div className="space-y-2">
                <Label htmlFor="pw">New password</Label>
                <Input
                  id="pw" type="password" autoComplete="new-password" required minLength={8}
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  data-testid="set-password-new-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pw2">Confirm password</Label>
                <Input
                  id="pw2" type="password" autoComplete="new-password" required minLength={8}
                  value={confirm} onChange={(e) => setConfirm(e.target.value)}
                  data-testid="set-password-confirm-input"
                />
              </div>
              {error ? (
                <Alert variant="destructive" data-testid="set-password-error">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}
              <Button
                type="submit" className="w-full" disabled={busy || !token}
                data-testid="set-password-submit-button"
              >
                {busy ? "Saving…" : "Save password"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
