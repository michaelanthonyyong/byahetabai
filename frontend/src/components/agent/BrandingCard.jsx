import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import { AgentLogo } from "@/components/agent/AgentBrand";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ImageUp, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";

const MAX = 2 * 1024 * 1024;

const LogoPicker = ({ profile }) => {
  const qc = useQueryClient();
  const input = useRef(null);
  const [busy, setBusy] = useState(false);
  const refresh = (p) => qc.setQueryData(["agent-profile"], p);

  const upload = async (file) => {
    if (!file) return;
    if (!["image/png", "image/jpeg"].includes(file.type)) { toast.error("Upload a PNG or JPG image."); return; }
    if (file.size > MAX) { toast.error("Logo must be 2 MB or smaller."); return; }
    setBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post("/agent/profile/logo", fd, { headers: { "Content-Type": "multipart/form-data" } });
      refresh(data.profile);
      toast.success("Logo updated.");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      const { data } = await api.delete("/agent/profile/logo");
      refresh(data.profile);
      toast.success("Logo removed.");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-4">
      <div className="h-20 w-20 shrink-0 rounded-xl border border-dashed border-stone-300 bg-stone-50 flex items-center justify-center overflow-hidden">
        {profile.has_logo ? <AgentLogo profile={profile} className="h-20 w-20" testid="profile-logo-preview" /> : <ImageUp size={22} className="text-stone-400" />}
      </div>
      <div className="space-y-2">
        <input ref={input} type="file" accept="image/png,image/jpeg" className="hidden" onChange={(e) => upload(e.target.files?.[0])} data-testid="profile-logo-input" />
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => input.current?.click()} disabled={busy} data-testid="profile-logo-upload">
            {busy ? <Loader2 size={14} className="animate-spin mr-1" /> : <ImageUp size={14} className="mr-1" />}{profile.has_logo ? "Replace logo" : "Upload logo"}
          </Button>
          {profile.has_logo ? <Button variant="ghost" size="sm" onClick={remove} disabled={busy} data-testid="profile-logo-remove"><Trash2 size={14} className="mr-1" />Remove</Button> : null}
        </div>
        <p className="text-xs text-stone-500">PNG or JPG, up to 2 MB.</p>
      </div>
    </div>
  );
};

const DEFAULT_COLOR = "#115e59";
const luminance = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

const ColorPicker = ({ profile }) => {
  const qc = useQueryClient();
  const [color, setColor] = useState(DEFAULT_COLOR);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setColor(profile.brand_color || DEFAULT_COLOR); }, [profile.brand_color]);
  const valid = /^#[0-9a-fA-F]{6}$/.test(color);
  const tooLight = valid && luminance(color) > 0.6;

  const save = async (value) => {
    setBusy(true);
    try {
      const { data } = await api.patch("/agent/profile", { brand_color: value });
      qc.setQueryData(["agent-profile"], data.profile);
      toast.success(value ? "Brand colour saved." : "Brand colour reset.");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2 sm:col-span-2 border-t border-stone-100 pt-5">
      <Label htmlFor="p-color">Brand colour</Label>
      <div className="flex flex-wrap items-center gap-3">
        <input id="p-color" type="color" value={valid ? color : DEFAULT_COLOR} onChange={(e) => setColor(e.target.value)}
          className="h-10 w-14 cursor-pointer rounded-md border border-stone-300 bg-white p-1" data-testid="profile-brand-color-picker" />
        <Input value={color} maxLength={7} onChange={(e) => setColor(e.target.value.trim())} className="w-32 font-mono" data-testid="profile-brand-color-input" />
        <div className="flex items-center gap-2 rounded-lg border border-stone-200 px-3 py-2" data-testid="profile-brand-color-preview">
          <span className="h-4 w-4 rounded" style={{ background: valid ? color : DEFAULT_COLOR }} />
          <span className="text-sm font-semibold" style={{ color: valid ? color : DEFAULT_COLOR }}>{profile.brand_name}</span>
        </div>
        <Button onClick={() => save(color)} disabled={!valid || busy} className="bg-teal-800 hover:bg-teal-900" data-testid="profile-brand-color-save">Save colour</Button>
        {profile.brand_color ? <Button variant="ghost" onClick={() => save("")} disabled={busy} data-testid="profile-brand-color-reset">Reset</Button> : null}
      </div>
      {!valid ? <p className="text-xs text-red-600" data-testid="profile-brand-color-error">Use a colour code like #1E40AF.</p> : null}
      {tooLight ? <p className="text-xs text-amber-700" data-testid="profile-brand-color-warning">This colour is very light — white text and headings may be hard to read on quotes and receipts.</p> : null}
      <p className="text-xs text-stone-500">Used on your quotes, receipts and portal buttons.</p>
    </div>
  );
};

export const BrandingCard = ({ profile }) => {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setName(profile.business_name || ""); }, [profile.business_name]);

  const save = async () => {
    setBusy(true);
    try {
      const { data } = await api.patch("/agent/profile", { business_name: name });
      qc.setQueryData(["agent-profile"], data.profile);
      toast.success("Business name saved.");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="border-stone-200 lg:col-span-2" data-testid="profile-branding-card">
      <CardHeader>
        <CardTitle className="text-base">Your business branding</CardTitle>
        <CardDescription>Shown on your portal and on every quote and receipt you give customers.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 sm:grid-cols-2">
        <LogoPicker profile={profile} />
        <div className="space-y-2">
          <Label htmlFor="p-business">Business name</Label>
          <Input id="p-business" maxLength={120} value={name} placeholder={profile.agency_name || ""} onChange={(e) => setName(e.target.value)} data-testid="profile-business-name-input" />
          <p className="text-xs text-stone-500">Leave blank to use "{profile.agency_name || profile.display_name}".</p>
          <Button onClick={save} disabled={busy} className="bg-teal-800 hover:bg-teal-900" data-testid="profile-business-name-save">
            {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}Save name
          </Button>
        </div>
        <ColorPicker profile={profile} />
      </CardContent>
    </Card>
  );
};
