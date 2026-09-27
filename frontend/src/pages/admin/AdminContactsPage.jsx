import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api, formatApiError } from "@/lib/api";
import { timeAgo } from "@/lib/admin";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Search, Loader2 } from "lucide-react";
import { toast } from "sonner";

const STATUS_TONES = {
  new: "bg-amber-100 text-amber-800",
  read: "bg-stone-200 text-stone-700",
  responded: "bg-emerald-100 text-emerald-800",
  archived: "bg-stone-100 text-stone-500",
};

const TABS = ["", "new", "read", "responded", "archived"];

export default function AdminContactsPage() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const status = params.get("status") || "";
  const q = params.get("q") || "";
  const [searchInput, setSearchInput] = useState(q);
  const [openId, setOpenId] = useState(null);

  const filters = useMemo(() => ({
    status: status || undefined,
    q: q || undefined,
  }), [status, q]);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-contacts", filters],
    queryFn: () => api.get("/admin/contacts", { params: filters }).then((r) => r.data),
  });

  const setParam = (k, v) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    setParams(next, { replace: true });
  };

  return (
    <AdminShell subtitle="Inbox" title="Contact Messages">
      <div className="space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="inline-flex rounded-lg border border-stone-200 bg-white p-1" data-testid="admin-contacts-tabs">
            {TABS.map((s) => (
              <button
                key={s}
                onClick={() => setParam("status", s)}
                data-testid={`admin-contacts-filter-${s || "all"}`}
                className={[
                  "px-3 py-1.5 text-sm rounded-md capitalize",
                  status === s ? "bg-stone-900 text-white" : "text-stone-600 hover:text-stone-900",
                ].join(" ")}
              >
                {s || "all"}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 py-1.5 min-w-0 sm:min-w-[280px]">
            <Search size={14} className="text-stone-400 shrink-0" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && setParam("q", searchInput.trim())}
              placeholder="Name, email, subject, message"
              className="w-full bg-transparent outline-none text-sm"
              data-testid="admin-contacts-search"
            />
          </label>
        </div>

        {isLoading ? (
          <div className="h-64 rounded-lg bg-stone-100 animate-pulse" />
        ) : !data?.contacts?.length ? (
          <div className="rounded-lg border border-dashed border-stone-200 p-10 text-center text-sm text-stone-500" data-testid="admin-contacts-empty">
            No messages match those filters.
          </div>
        ) : (
          <>
            <div className="text-xs text-stone-500">
              {data.total} total · showing {data.contacts.length}
              {data.new_count > 0 ? <span className="ml-2 text-amber-600">· {data.new_count} new</span> : null}
            </div>
            <Card>
              <CardContent className="p-0 overflow-x-auto">
                <table className="w-full text-sm min-w-[900px]" data-testid="admin-contacts-table">
                  <thead className="border-b border-stone-200 bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                    <tr>
                      <th className="px-4 py-3 text-left">From</th>
                      <th className="px-4 py-3 text-left">Subject / Message</th>
                      <th className="px-4 py-3 text-left">Package</th>
                      <th className="px-4 py-3 text-left">Received</th>
                      <th className="px-4 py-3 text-left">Status</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.contacts.map((c) => (
                      <tr key={c.id} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`admin-contact-row-${c.id}`}>
                        <td className="px-4 py-3">
                          <div className="text-stone-900">{c.name}</div>
                          <div className="text-xs text-stone-500">{c.email}</div>
                          {c.phone ? <div className="text-xs text-stone-400">{c.phone}</div> : null}
                        </td>
                        <td className="px-4 py-3 max-w-[420px]">
                          {c.subject ? <div className="text-stone-800 truncate">{c.subject}</div> : null}
                          <div className="text-xs text-stone-500 truncate">{c.message}</div>
                        </td>
                        <td className="px-4 py-3 text-xs font-mono text-stone-600">{c.package_slug || "—"}</td>
                        <td className="px-4 py-3 text-xs text-stone-500 whitespace-nowrap">{timeAgo(c.created_at)}</td>
                        <td className="px-4 py-3">
                          <Badge className={STATUS_TONES[c.status]}>{c.status}</Badge>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setOpenId(c.id)}
                            data-testid={`admin-contact-open-${c.id}`}
                          >
                            Open
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {openId ? (
        <ContactDialog
          id={openId}
          onClose={() => setOpenId(null)}
          onDone={() => {
            qc.invalidateQueries({ queryKey: ["admin-contacts"] });
            qc.invalidateQueries({ queryKey: ["admin-dashboard"] });
          }}
        />
      ) : null}
    </AdminShell>
  );
}

function ContactDialog({ id, onClose, onDone }) {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-contact", id],
    queryFn: () => api.get(`/admin/contacts/${id}`).then((r) => r.data),
  });
  const c = data?.contact;
  const initialNote = c?.internal_note || "";
  const [status, setStatus] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [initialised, setInitialised] = useState(false);

  useEffect(() => {
    if (c && !initialised) {
      setStatus(c.status || "read");
      setNote(c.internal_note || "");
      setInitialised(true);
    }
  }, [c, initialised]);

  const save = async () => {
    if (!c) return;
    setBusy(true);
    try {
      await api.patch(`/admin/contacts/${c.id}`, {
        status: status || undefined,
        internal_note: note !== initialNote ? note : undefined,
      });
      toast.success("Contact updated.");
      onDone();
      onClose();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-2xl" data-testid="admin-contact-dialog">
        <DialogHeader>
          <DialogTitle>{isLoading ? "Loading…" : c?.subject || `Message from ${c?.name}`}</DialogTitle>
          <DialogDescription>
            {c ? <>{c.name} · {c.email}{c.phone ? ` · ${c.phone}` : ""}</> : null}
          </DialogDescription>
        </DialogHeader>
        {c ? (
          <div className="space-y-4">
            <div className="rounded-md border border-stone-200 bg-stone-50 p-3 text-sm whitespace-pre-wrap" data-testid="admin-contact-message">
              {c.message}
            </div>
            {c.package_slug ? (
              <div className="text-xs text-stone-500">Package: <span className="font-mono">{c.package_slug}</span></div>
            ) : null}
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label>Status</Label>
                <Select value={status || "read"} onValueChange={setStatus}>
                  <SelectTrigger data-testid="admin-contact-status"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="new">New</SelectItem>
                    <SelectItem value="read">Read</SelectItem>
                    <SelectItem value="responded">Responded</SelectItem>
                    <SelectItem value="archived">Archived</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="text-xs text-stone-500 self-end">
                Received {timeAgo(c.created_at)}
              </div>
            </div>
            <div>
              <Label htmlFor="cnote">Internal note</Label>
              <Textarea
                id="cnote" rows={3}
                value={note} onChange={(e) => setNote(e.target.value)}
                maxLength={2000}
                placeholder="Private notes for the admin team (not visible to the guest)."
                data-testid="admin-contact-note"
              />
            </div>
          </div>
        ) : null}
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={busy}>Close</Button>
          <Button onClick={save} disabled={busy || !c} data-testid="admin-contact-save">
            {busy ? <Loader2 className="animate-spin mr-1" size={14} /> : null}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// (helpers removed — status/note are initialised via useEffect above)
