import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api, formatApiError } from "@/lib/api";
import { timeAgo } from "@/lib/admin";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function AdminSettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["admin-settings"],
    queryFn: () => api.get("/admin/settings").then((r) => r.data),
  });

  const settings = data?.settings || {};

  const save = async (key, value) => {
    try {
      await api.put(`/admin/settings/${key}`, { value });
      toast.success("Setting updated.");
      qc.invalidateQueries({ queryKey: ["admin-settings"] });
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  return (
    <AdminShell subtitle="System" title="Settings">
      <div className="space-y-6 max-w-3xl">
        <Alert>
          <AlertDescription className="text-xs">
            Only the settings below can be edited here. Every change is validated and written to the audit log.
          </AlertDescription>
        </Alert>

        {isLoading ? (
          <div className="h-40 rounded-lg bg-stone-100 animate-pulse" />
        ) : (
          <>
            {settings.brand ? <BrandCard setting={settings.brand} onSave={save} /> : null}
            {settings.minimum_topup_amount ? (
              <MoneyCard setting={settings.minimum_topup_amount} onSave={save} testid="minimum_topup_amount" />
            ) : null}
            {settings.maximum_topup_amount ? (
              <MoneyCard setting={settings.maximum_topup_amount} onSave={save} testid="maximum_topup_amount" />
            ) : null}
            {settings.commission_withdrawals_enabled ? (
              <ToggleCard setting={settings.commission_withdrawals_enabled} onSave={save} />
            ) : null}
          </>
        )}
      </div>
    </AdminShell>
  );
}

/* --- Cards -------------------------------------------------------------- */

function BrandCard({ setting, onSave }) {
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setForm({
      name: setting.value?.name || "",
      tagline: setting.value?.tagline || "",
      currency: setting.value?.currency || "PHP",
      support_email: setting.value?.support_email || "",
      support_phone: setting.value?.support_phone || "",
    });
  }, [setting.updated_at]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    setBusy(true);
    await onSave("brand", form);
    setBusy(false);
  };

  return (
    <Card data-testid="settings-brand-card">
      <CardHeader>
        <CardTitle className="text-base">{setting.label}</CardTitle>
        <CardDescription>{setting.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="b-name">Business name</Label>
            <Input id="b-name" value={form.name || ""} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="settings-brand-name" />
          </div>
          <div>
            <Label htmlFor="b-tagline">Tagline</Label>
            <Input id="b-tagline" value={form.tagline || ""} onChange={(e) => setForm((f) => ({ ...f, tagline: e.target.value }))} data-testid="settings-brand-tagline" />
          </div>
          <div>
            <Label htmlFor="b-currency">Currency</Label>
            <Input id="b-currency" value={form.currency || ""} onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value }))} />
          </div>
          <div>
            <Label htmlFor="b-email">Support email</Label>
            <Input id="b-email" type="email" value={form.support_email || ""} onChange={(e) => setForm((f) => ({ ...f, support_email: e.target.value }))} />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="b-phone">Support phone</Label>
            <Input id="b-phone" value={form.support_phone || ""} onChange={(e) => setForm((f) => ({ ...f, support_phone: e.target.value }))} />
          </div>
        </div>
        <div className="flex items-center justify-between pt-2">
          <div className="text-[11px] text-stone-500">Updated {timeAgo(setting.updated_at)}</div>
          <Button onClick={submit} disabled={busy} data-testid="settings-brand-save">
            {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}Save brand
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function MoneyCard({ setting, onSave, testid }) {
  const [value, setValue] = useState(setting.value || "");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setValue(setting.value || ""); }, [setting.updated_at]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    setBusy(true);
    await onSave(setting.key, value);
    setBusy(false);
  };

  return (
    <Card data-testid={`settings-${testid}-card`}>
      <CardHeader>
        <CardTitle className="text-base">{setting.label}</CardTitle>
        <CardDescription>{setting.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex items-end gap-3">
        <div className="flex-1">
          <Label htmlFor={`v-${setting.key}`}>Amount (PHP)</Label>
          <Input
            id={`v-${setting.key}`}
            type="number" min="1" step="0.01"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            data-testid={`settings-${testid}-input`}
          />
        </div>
        <Button onClick={submit} disabled={busy} data-testid={`settings-${testid}-save`}>
          {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}Save
        </Button>
      </CardContent>
    </Card>
  );
}

function ToggleCard({ setting, onSave }) {
  const [busy, setBusy] = useState(false);
  const toggle = async (v) => {
    setBusy(true);
    await onSave(setting.key, v);
    setBusy(false);
  };
  return (
    <Card data-testid="settings-withdrawals-card">
      <CardHeader>
        <CardTitle className="text-base">{setting.label}</CardTitle>
        <CardDescription>{setting.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-between">
        <div className="text-sm text-stone-600">
          Currently <b>{setting.value ? "enabled" : "disabled"}</b>
        </div>
        <Switch
          checked={!!setting.value}
          onCheckedChange={toggle}
          disabled={busy}
          data-testid="settings-withdrawals-toggle"
        />
      </CardContent>
    </Card>
  );
}
