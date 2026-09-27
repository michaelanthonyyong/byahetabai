import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

const SCOPE_TONES = {
  international: "bg-sky-100 text-sky-800",
  domestic: "bg-emerald-100 text-emerald-800",
};

function DestinationDialog({ initial, onDone }) {
  const isEdit = !!initial;
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(initial || {
    slug: "", name: "", country: "", scope: "international",
    hero_image_url: "", short_description: "", long_description: "",
    featured_on_home: false, is_active: true,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (isEdit) {
        const patch = { ...form };
        delete patch.slug;
        await api.patch(`/admin/destinations/${initial.id}`, patch);
        toast.success("Destination updated");
      } else {
        await api.post("/admin/destinations", form);
        toast.success("Destination created");
      }
      setOpen(false);
      onDone?.();
    } catch (err) { setError(formatApiError(err)); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {isEdit ? (
          <Button size="sm" variant="outline" data-testid={`admin-destination-edit-${initial.id}`}>Edit</Button>
        ) : (
          <Button data-testid="admin-destination-new-button"><Plus size={14} className="mr-1" />New destination</Button>
        )}
      </DialogTrigger>
      <DialogContent data-testid="admin-destination-dialog">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit destination" : "New destination"}</DialogTitle>
          <DialogDescription>Public catalog entity that groups tour packages.</DialogDescription>
        </DialogHeader>
        <form className="space-y-3" onSubmit={submit}>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2"><Label>Slug</Label>
              <Input value={form.slug} disabled={isEdit}
                onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") })}
                data-testid="admin-destination-slug-input" required /></div>
            <div className="space-y-2"><Label>Name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                data-testid="admin-destination-name-input" required /></div>
            <div className="space-y-2"><Label>Country</Label>
              <Input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })}
                data-testid="admin-destination-country-input" required /></div>
            <div className="space-y-2"><Label>Scope</Label>
              <Select value={form.scope} onValueChange={(v) => setForm({ ...form, scope: v })}>
                <SelectTrigger data-testid="admin-destination-scope-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="international">International</SelectItem>
                  <SelectItem value="domestic">Domestic</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2"><Label>Hero image URL</Label>
            <Input value={form.hero_image_url || ""} onChange={(e) => setForm({ ...form, hero_image_url: e.target.value })}
              placeholder="https://…" data-testid="admin-destination-hero-input" /></div>
          <div className="space-y-2"><Label>Short description</Label>
            <Textarea rows={2} value={form.short_description || ""} onChange={(e) => setForm({ ...form, short_description: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!form.featured_on_home}
                onChange={(e) => setForm({ ...form, featured_on_home: e.target.checked })} />
              Feature on home
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              Active
            </label>
          </div>
          {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
          <DialogFooter>
            <Button type="submit" disabled={busy} data-testid="admin-destination-submit-button">
              {busy ? "Saving…" : (isEdit ? "Save" : "Create")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function AdminDestinationsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["admin-destinations"],
    queryFn: () => api.get("/admin/destinations").then((r) => r.data.destinations),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin-destinations"] });

  const remove = async (d) => {
    if (!window.confirm(`Delete "${d.name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/admin/destinations/${d.id}`);
      toast.success("Destination deleted");
      refresh();
    } catch (err) { toast.error(formatApiError(err)); }
  };

  return (
    <AdminShell subtitle="Catalog" title="Destinations" actions={<DestinationDialog onDone={refresh} />}>
      <div className="space-y-6">
        {isLoading ? (
          <div className="h-64 rounded-lg bg-stone-100 animate-pulse" />
        ) : !data?.length ? (
          <div className="rounded-lg border border-dashed border-stone-200 p-10 text-center text-sm text-stone-500">
            No destinations yet.
          </div>
        ) : (
          <Card>
            <CardContent className="p-0 overflow-x-auto">
              <table className="w-full text-sm min-w-[720px]" data-testid="admin-destinations-table">
                <thead className="border-b border-stone-200 bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                  <tr>
                    <th className="px-4 py-3 text-left">Destination</th>
                    <th className="px-4 py-3 text-left">Scope</th>
                    <th className="px-4 py-3 text-left">Active</th>
                    <th className="px-4 py-3 text-left">Featured</th>
                    <th className="px-4 py-3 text-right">Packages</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((d) => {
                    const totalPkgs = Object.values(d.package_counts || {}).reduce((a, b) => a + b, 0);
                    return (
                      <tr key={d.id} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`admin-destination-row-${d.id}`}>
                        <td className="px-4 py-3">
                          <div className="font-medium">{d.name}</div>
                          <div className="text-xs text-stone-500">{d.country} · <span className="font-mono">{d.slug}</span></div>
                        </td>
                        <td className="px-4 py-3"><Badge className={SCOPE_TONES[d.scope]}>{d.scope}</Badge></td>
                        <td className="px-4 py-3">{d.is_active ? "Yes" : <span className="text-stone-400">No</span>}</td>
                        <td className="px-4 py-3">{d.featured_on_home ? "★" : "—"}</td>
                        <td className="px-4 py-3 text-right">
                          {totalPkgs}
                          {d.package_counts?.draft ? <span className="ml-2 text-xs text-stone-500">({d.package_counts.draft} draft)</span> : null}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="inline-flex gap-2">
                            <DestinationDialog initial={d} onDone={refresh} />
                            <Button size="sm" variant="ghost" onClick={() => remove(d)} disabled={totalPkgs > 0}
                              data-testid={`admin-destination-delete-${d.id}`}>
                              <Trash2 size={14} className="text-red-600" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}
      </div>
    </AdminShell>
  );
}
