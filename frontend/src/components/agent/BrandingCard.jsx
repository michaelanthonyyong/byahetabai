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
      </CardContent>
    </Card>
  );
};
