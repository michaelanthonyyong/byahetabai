import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import AgentShell from "@/components/agent/AgentShell";
import { BrandingCard } from "@/components/agent/BrandingCard";
import { SharedLinksCard } from "@/components/agent/SharedLinksCard";
import { useAgentProfile } from "@/components/agent/AgentBrand";
import { api, formatApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

const ReadOnly = ({ label, value, testid }) => (
  <div className="min-w-0">
    <div className="text-[11px] uppercase tracking-widest text-stone-500">{label}</div>
    <div className="text-sm text-stone-900 mt-0.5 break-all" data-testid={testid}>{value || "—"}</div>
  </div>
);

const ContactForm = ({ profile }) => {
  const qc = useQueryClient();
  const [form, setForm] = useState({ phone: "", address: "" });
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setForm({ phone: profile.phone || "", address: profile.address || "" });
  }, [profile]);
  const save = async () => {
    setBusy(true);
    try {
      await api.patch("/agent/profile", form);
      toast.success("Profile updated.");
      qc.invalidateQueries({ queryKey: ["agent-profile"] });
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-3">
      <div><Label htmlFor="p-phone">Phone</Label><Input id="p-phone" maxLength={40} value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} data-testid="profile-phone-input" /></div>
      <div><Label htmlFor="p-address">Address</Label><Input id="p-address" maxLength={300} value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} data-testid="profile-address-input" /></div>
      <Button onClick={save} disabled={busy} className="bg-teal-800 hover:bg-teal-900" data-testid="profile-save">
        {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}Save details
      </Button>
    </div>
  );
};

const PasswordForm = () => {
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const mismatch = form.confirm && form.confirm !== form.new_password;
  const save = async () => {
    setBusy(true);
    try {
      await api.post("/auth/change-password", { current_password: form.current_password, new_password: form.new_password });
      toast.success("Password changed.");
      setForm({ current_password: "", new_password: "", confirm: "" });
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  return (
    <div className="space-y-3">
      <div><Label htmlFor="pw-cur">Current password</Label><Input id="pw-cur" type="password" value={form.current_password} onChange={set("current_password")} data-testid="profile-current-password" /></div>
      <div><Label htmlFor="pw-new">New password (min 8 characters)</Label><Input id="pw-new" type="password" value={form.new_password} onChange={set("new_password")} data-testid="profile-new-password" /></div>
      <div><Label htmlFor="pw-conf">Confirm new password</Label><Input id="pw-conf" type="password" value={form.confirm} onChange={set("confirm")} data-testid="profile-confirm-password" />
        {mismatch ? <div className="text-xs text-red-600 mt-1" data-testid="profile-password-mismatch">Passwords don't match.</div> : null}</div>
      <Button onClick={save} disabled={busy || mismatch || form.new_password.length < 8 || !form.current_password} variant="outline" data-testid="profile-change-password">
        {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}Change password
      </Button>
    </div>
  );
};

export default function AgentProfilePage() {
  const { data, isLoading } = useAgentProfile();
  return (
    <AgentShell subtitle="Account" title="My profile">
      {isLoading || !data ? <div className="h-40 rounded-xl bg-stone-100 animate-pulse max-w-4xl" /> : (
        <div className="grid gap-6 lg:grid-cols-2 max-w-4xl">
          <Card className="border-stone-200 lg:col-span-2">
            <CardContent className="p-5 grid gap-4 sm:grid-cols-4">
              <ReadOnly label="Name" value={data.display_name} testid="profile-name" />
              <ReadOnly label="Agency" value={data.agency_name} testid="profile-agency" />
              <ReadOnly label="Email" value={data.email} testid="profile-email" />
              <ReadOnly label="Member since" value={data.member_since ? new Date(data.member_since).toLocaleDateString() : ""} />
            </CardContent>
          </Card>
          <BrandingCard profile={data} />
          <SharedLinksCard />
          <Card className="border-stone-200">
            <CardHeader><CardTitle className="text-base">Contact details</CardTitle><CardDescription>Name and agency are managed by the admin.</CardDescription></CardHeader>
            <CardContent><ContactForm profile={data} /></CardContent>
          </Card>
          <Card className="border-stone-200">
            <CardHeader><CardTitle className="text-base">Password</CardTitle></CardHeader>
            <CardContent><PasswordForm /></CardContent>
          </Card>
        </div>
      )}
    </AgentShell>
  );
}
