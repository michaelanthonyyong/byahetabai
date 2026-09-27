import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api, formatApiError } from "@/lib/api";
import { formatPHP } from "@/lib/admin";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { ArrowLeft, Trash2, Plus, ArrowUp, ArrowDown, Star } from "lucide-react";
import { toast } from "sonner";

const STATUS_TONES = {
  draft: "bg-stone-200 text-stone-700",
  published: "bg-emerald-100 text-emerald-800",
  archived: "bg-amber-100 text-amber-800",
};

const emptyForm = () => ({
  slug: "", title: "", destination_id: "",
  guest_price: "", agent_cost: "", commission_amount: "",
  duration_days: 3, duration_nights: 2, min_pax: 1, max_pax: 20,
  summary: "", highlights: "", itinerary: "",
  images: [], inclusions: [], exclusions: [],
  is_featured: false,
});

function useDestinations() {
  return useQuery({
    queryKey: ["admin-destinations-select"],
    queryFn: () => api.get("/admin/destinations").then((r) => r.data.destinations),
  });
}

/* --- reorderable child lists ----------------------------------------- */

function TextRowsEditor({ items, setItems, placeholder, testid }) {
  const add = () => setItems([...items, { text: "", sort_order: items.length }]);
  const remove = (i) => setItems(items.filter((_, idx) => idx !== i));
  const move = (i, dir) => {
    const j = i + dir;
    if (j < 0 || j >= items.length) return;
    const next = [...items];
    [next[i], next[j]] = [next[j], next[i]];
    next.forEach((it, idx) => (it.sort_order = idx));
    setItems(next);
  };
  const set = (i, text) => setItems(items.map((it, idx) => (idx === i ? { ...it, text } : it)));
  return (
    <div className="space-y-2" data-testid={testid}>
      {items.length === 0 ? (
        <div className="text-xs text-stone-500">Nothing yet.</div>
      ) : null}
      {items.map((it, i) => (
        <div key={it.id || i} className="flex items-center gap-2">
          <Input value={it.text} placeholder={placeholder}
            onChange={(e) => set(i, e.target.value)}
            data-testid={`${testid}-input-${i}`} />
          <Button type="button" size="icon" variant="ghost" onClick={() => move(i, -1)} title="Move up"><ArrowUp size={14} /></Button>
          <Button type="button" size="icon" variant="ghost" onClick={() => move(i, 1)} title="Move down"><ArrowDown size={14} /></Button>
          <Button type="button" size="icon" variant="ghost" onClick={() => remove(i)} title="Remove" data-testid={`${testid}-remove-${i}`}><Trash2 size={14} className="text-red-600" /></Button>
        </div>
      ))}
      <Button type="button" size="sm" variant="outline" onClick={add} data-testid={`${testid}-add`}>
        <Plus size={14} className="mr-1" />Add
      </Button>
    </div>
  );
}

function ImagesEditor({ items, setItems }) {
  const add = () => setItems([...items, { url: "", alt: "", is_cover: items.length === 0, sort_order: items.length }]);
  const remove = (i) => setItems(items.filter((_, idx) => idx !== i));
  const set = (i, k, v) => setItems(items.map((it, idx) => (idx === i ? { ...it, [k]: v } : it)));
  const promote = (i) => setItems(items.map((it, idx) => ({ ...it, is_cover: idx === i })));
  return (
    <div className="space-y-3" data-testid="admin-package-images">
      {items.length === 0 ? <div className="text-xs text-stone-500">No images yet. Add at least one before publishing.</div> : null}
      {items.map((it, i) => (
        <div key={it.id || i} className="flex flex-col gap-2 rounded-lg border border-stone-200 bg-white p-3 sm:flex-row sm:items-center">
          <div className="w-20 h-16 flex-shrink-0 overflow-hidden rounded bg-stone-100">
            {it.url ? <img src={it.url} className="h-full w-full object-cover" alt={it.alt || ""} /> : null}
          </div>
          <div className="flex-1 grid gap-2 sm:grid-cols-[1fr,auto]">
            <Input placeholder="https://…" value={it.url} onChange={(e) => set(i, "url", e.target.value)}
              data-testid={`admin-package-image-url-${i}`} />
            <Input placeholder="alt text" value={it.alt || ""} onChange={(e) => set(i, "alt", e.target.value)}
              className="sm:w-40" />
          </div>
          <div className="flex items-center gap-1">
            <Button type="button" size="icon" variant={it.is_cover ? "default" : "outline"} onClick={() => promote(i)} title="Set as cover" data-testid={`admin-package-image-cover-${i}`}>
              <Star size={14} className={it.is_cover ? "" : "text-stone-500"} />
            </Button>
            <Button type="button" size="icon" variant="ghost" onClick={() => remove(i)} title="Remove" data-testid={`admin-package-image-remove-${i}`}>
              <Trash2 size={14} className="text-red-600" />
            </Button>
          </div>
        </div>
      ))}
      <Button type="button" size="sm" variant="outline" onClick={add} data-testid="admin-package-image-add">
        <Plus size={14} className="mr-1" />Add image
      </Button>
    </div>
  );
}

/* --- main page ------------------------------------------------------- */

export default function AdminPackageEditorPage() {
  const { id } = useParams();
  const isNew = id === "new";
  const qc = useQueryClient();
  const navigate = useNavigate();

  const dests = useDestinations();
  const existing = useQuery({
    queryKey: ["admin-package", id],
    queryFn: () => api.get(`/admin/packages/${id}`).then((r) => r.data.package),
    enabled: !isNew,
  });

  const [form, setForm] = useState(emptyForm());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (isNew || !existing.data) return;
    const p = existing.data;
    setForm({
      slug: p.slug, title: p.title, destination_id: p.destination_id,
      guest_price: p.guest_price, agent_cost: p.agent_cost, commission_amount: p.commission_amount,
      duration_days: p.duration_days ?? 3, duration_nights: p.duration_nights ?? 2,
      min_pax: p.min_pax ?? 1, max_pax: p.max_pax ?? 20,
      summary: p.summary || "", highlights: p.highlights || "", itinerary: p.itinerary || "",
      images: p.images || [], inclusions: p.inclusions || [], exclusions: p.exclusions || [],
      is_featured: !!p.is_featured,
    });
  }, [isNew, existing.data]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setError("");
    setBusy(true);
    try {
      if (isNew) {
        const { data } = await api.post("/admin/packages", form);
        toast.success("Draft created");
        qc.invalidateQueries({ queryKey: ["admin-packages"] });
        navigate(`/admin/packages/${data.package.id}`, { replace: true });
      } else {
        const patch = { ...form };
        delete patch.slug;
        await api.patch(`/admin/packages/${id}`, patch);
        toast.success("Saved");
        qc.invalidateQueries({ queryKey: ["admin-package", id] });
        qc.invalidateQueries({ queryKey: ["admin-packages"] });
      }
    } catch (err) {
      setError(formatApiError(err));
    } finally { setBusy(false); }
  };

  const changeStatus = async (target) => {
    try {
      await api.post(`/admin/packages/${id}/status`, { status: target });
      toast.success(`Package ${target}`);
      qc.invalidateQueries({ queryKey: ["admin-package", id] });
      qc.invalidateQueries({ queryKey: ["admin-packages"] });
    } catch (err) { toast.error(formatApiError(err)); }
  };

  if (!isNew && existing.isLoading) {
    return <AdminShell title="Package"><div className="h-64 rounded-lg bg-stone-100 animate-pulse" /></AdminShell>;
  }
  if (!isNew && existing.isError) {
    return (
      <AdminShell title="Package">
        <div className="text-sm text-stone-600" data-testid="admin-package-not-found">
          Package not found. <Link className="underline" to="/admin/packages">Back</Link>
        </div>
      </AdminShell>
    );
  }

  const p = existing.data;

  return (
    <AdminShell
      subtitle={<Link to="/admin/packages" className="inline-flex items-center gap-1 hover:underline"><ArrowLeft size={12}/>Packages</Link>}
      title={isNew ? "New package" : (form.title || p?.title || "Package")}
      actions={
        <div className="flex flex-wrap gap-2">
          {!isNew && p ? (
            <>
              <Badge className={STATUS_TONES[p.status]}>{p.status}</Badge>
              {p.status !== "published" ? (
                <Button variant="default" onClick={() => changeStatus("published")} data-testid="admin-package-publish-button">Publish</Button>
              ) : null}
              {p.status !== "archived" ? (
                <Button variant="outline" onClick={() => changeStatus("archived")} data-testid="admin-package-archive-button">Archive</Button>
              ) : null}
            </>
          ) : null}
          <Button onClick={save} disabled={busy} data-testid="admin-package-save">
            {busy ? "Saving…" : (isNew ? "Create draft" : "Save changes")}
          </Button>
        </div>
      }
    >
      {error ? (
        <Alert variant="destructive" className="mb-6" data-testid="admin-package-error">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <Tabs defaultValue="basics" data-testid="admin-package-tabs">
        <TabsList>
          <TabsTrigger value="basics">Basics</TabsTrigger>
          <TabsTrigger value="pricing">Pricing</TabsTrigger>
          <TabsTrigger value="content">Content</TabsTrigger>
          <TabsTrigger value="media">Media</TabsTrigger>
          <TabsTrigger value="inclusions">Inclusions</TabsTrigger>
          <TabsTrigger value="exclusions">Exclusions</TabsTrigger>
        </TabsList>

        <TabsContent value="basics" className="mt-4">
          <Card><CardHeader><CardTitle>Basics</CardTitle>
            <CardDescription>Public identity and destination.</CardDescription></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2 sm:col-span-2">
                <Label>Title</Label>
                <Input value={form.title} onChange={(e) => set("title", e.target.value)}
                  data-testid="admin-package-title-input" />
              </div>
              <div className="space-y-2">
                <Label>Slug (URL) {isNew ? "" : <span className="text-xs text-stone-400">read-only</span>}</Label>
                <Input value={form.slug} disabled={!isNew}
                  onChange={(e) => set("slug", e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                  data-testid="admin-package-slug-input" />
              </div>
              <div className="space-y-2">
                <Label>Destination</Label>
                <Select value={form.destination_id} onValueChange={(v) => set("destination_id", v)}>
                  <SelectTrigger data-testid="admin-package-destination-select"><SelectValue placeholder="Choose a destination" /></SelectTrigger>
                  <SelectContent>
                    {(dests.data || []).map((d) => (
                      <SelectItem key={d.id} value={d.id}>{d.name} · {d.scope}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2"><Label>Duration (days)</Label>
                <Input type="number" min={1} max={90} value={form.duration_days}
                  onChange={(e) => set("duration_days", parseInt(e.target.value) || 1)}
                  data-testid="admin-package-days-input" /></div>
              <div className="space-y-2"><Label>Nights</Label>
                <Input type="number" min={0} max={90} value={form.duration_nights}
                  onChange={(e) => set("duration_nights", parseInt(e.target.value) || 0)} /></div>
              <div className="space-y-2"><Label>Min pax</Label>
                <Input type="number" min={1} value={form.min_pax}
                  onChange={(e) => set("min_pax", parseInt(e.target.value) || 1)} /></div>
              <div className="space-y-2"><Label>Max pax</Label>
                <Input type="number" min={1} value={form.max_pax}
                  onChange={(e) => set("max_pax", parseInt(e.target.value) || 1)} /></div>
              <label className="sm:col-span-2 flex items-center gap-2 pt-2">
                <input type="checkbox" checked={form.is_featured}
                  onChange={(e) => set("is_featured", e.target.checked)}
                  data-testid="admin-package-featured-checkbox" />
                <span className="text-sm">Feature on homepage</span>
              </label>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="pricing" className="mt-4">
          <Card><CardHeader><CardTitle>Pricing</CardTitle>
            <CardDescription>All values in PHP. Guest price is public; agent cost and commission are internal.</CardDescription></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2"><Label>Guest price (per pax)</Label>
                <Input type="number" step="0.01" min="0" value={form.guest_price}
                  onChange={(e) => set("guest_price", e.target.value)}
                  data-testid="admin-package-guest-price-input" />
                <div className="text-xs text-stone-500">Displayed as {formatPHP(form.guest_price) || "—"}</div>
              </div>
              <div className="space-y-2"><Label>Agent cost (per pax)</Label>
                <Input type="number" step="0.01" min="0" value={form.agent_cost}
                  onChange={(e) => set("agent_cost", e.target.value)}
                  data-testid="admin-package-agent-cost-input" />
                <div className="text-xs text-stone-500">Debited on booking</div>
              </div>
              <div className="space-y-2"><Label>Commission (per pax)</Label>
                <Input type="number" step="0.01" min="0" value={form.commission_amount}
                  onChange={(e) => set("commission_amount", e.target.value)}
                  data-testid="admin-package-commission-input" />
                <div className="text-xs text-stone-500">Accrued on confirmation</div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="content" className="mt-4">
          <Card><CardHeader><CardTitle>Content</CardTitle>
            <CardDescription>Public copy shown on the package detail page.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2"><Label>Summary</Label>
                <Textarea rows={2} value={form.summary} onChange={(e) => set("summary", e.target.value)}
                  data-testid="admin-package-summary-input" /></div>
              <div className="space-y-2"><Label>Highlights</Label>
                <Textarea rows={4} value={form.highlights} onChange={(e) => set("highlights", e.target.value)} /></div>
              <div className="space-y-2"><Label>Itinerary</Label>
                <Textarea rows={10} value={form.itinerary} onChange={(e) => set("itinerary", e.target.value)}
                  data-testid="admin-package-itinerary-input" /></div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="media" className="mt-4">
          <Card><CardHeader><CardTitle>Images</CardTitle>
            <CardDescription>Paste an image URL. Star ★ marks the cover shown on cards.</CardDescription></CardHeader>
            <CardContent><ImagesEditor items={form.images} setItems={(v) => set("images", v)} /></CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="inclusions" className="mt-4">
          <Card><CardHeader><CardTitle>Inclusions</CardTitle>
            <CardDescription>What's included in the package.</CardDescription></CardHeader>
            <CardContent><TextRowsEditor items={form.inclusions} setItems={(v) => set("inclusions", v)}
              placeholder="e.g. Round-trip airfare"
              testid="admin-package-inclusions" /></CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="exclusions" className="mt-4">
          <Card><CardHeader><CardTitle>Exclusions</CardTitle>
            <CardDescription>What's not included.</CardDescription></CardHeader>
            <CardContent><TextRowsEditor items={form.exclusions} setItems={(v) => set("exclusions", v)}
              placeholder="e.g. Travel insurance"
              testid="admin-package-exclusions" /></CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </AdminShell>
  );
}
