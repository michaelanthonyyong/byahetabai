import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AdminShell from "@/components/admin/AdminShell";
import { api, formatApiError } from "@/lib/api";
import { formatPHP } from "@/lib/admin";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Search, Plus, MoreHorizontal, Send, Archive, FileEdit } from "lucide-react";
import { toast } from "sonner";

const STATUS_TONES = {
  draft: "bg-stone-200 text-stone-700",
  published: "bg-emerald-100 text-emerald-800",
  archived: "bg-amber-100 text-amber-800",
};

export default function AdminPackagesPage() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const status = params.get("status") || "";
  const [q, setQ] = useState(params.get("q") || "");
  const filters = useMemo(
    () => ({ status: status || undefined, q: params.get("q") || undefined }),
    [status, params],
  );
  useEffect(() => { setQ(params.get("q") || ""); }, [params]);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-packages", filters],
    queryFn: () => api.get("/admin/packages", { params: filters }).then((r) => r.data),
  });

  const setParam = (k, v) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    setParams(next, { replace: true });
  };

  const changeStatus = async (id, target) => {
    try {
      await api.post(`/admin/packages/${id}/status`, { status: target });
      toast.success(`Package ${target}`);
      qc.invalidateQueries({ queryKey: ["admin-packages"] });
      qc.invalidateQueries({ queryKey: ["admin-dashboard"] });
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const remove = async (id, title) => {
    if (!window.confirm(`Delete "${title}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/admin/packages/${id}`);
      toast.success("Package deleted");
      qc.invalidateQueries({ queryKey: ["admin-packages"] });
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const tabs = ["", "draft", "published", "archived"];

  return (
    <AdminShell
      subtitle="Catalog"
      title="Packages"
      actions={
        <Button asChild data-testid="admin-package-new-button">
          <Link to="/admin/packages/new"><Plus size={16} className="mr-1.5" />New package</Link>
        </Button>
      }
    >
      <div className="space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="inline-flex rounded-lg border border-stone-200 bg-white p-1" data-testid="admin-packages-status-tabs">
            {tabs.map((s) => (
              <button key={s} onClick={() => setParam("status", s)}
                data-testid={`admin-packages-filter-${s || "all"}`}
                className={[
                  "px-3 py-1.5 text-sm rounded-md capitalize",
                  status === s ? "bg-stone-900 text-white" : "text-stone-600 hover:text-stone-900",
                ].join(" ")}
              >{s || "all"}</button>
            ))}
          </div>
          <label className="flex items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 py-1.5 min-w-0 sm:min-w-[280px]">
            <Search size={14} className="text-stone-400 shrink-0" />
            <input value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && setParam("q", q.trim())}
              placeholder="Search slug or title"
              className="w-full bg-transparent outline-none text-sm"
              data-testid="admin-packages-search-input" />
          </label>
        </div>

        {isLoading ? (
          <div className="h-64 rounded-lg bg-stone-100 animate-pulse" />
        ) : !data?.packages?.length ? (
          <div className="rounded-lg border border-dashed border-stone-200 p-10 text-center text-sm text-stone-500" data-testid="admin-packages-empty">
            No packages match those filters.
          </div>
        ) : (
          <>
            <div className="text-xs text-stone-500">{data.total} total · showing {data.packages.length}</div>
            <Card>
              <CardContent className="p-0 overflow-x-auto">
                <table className="w-full text-sm min-w-[900px]" data-testid="admin-packages-table">
                  <thead className="border-b border-stone-200 bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                    <tr>
                      <th className="px-4 py-3 text-left">Package</th>
                      <th className="px-4 py-3 text-left">Destination</th>
                      <th className="px-4 py-3 text-left">Status</th>
                      <th className="px-4 py-3 text-right">Guest price</th>
                      <th className="px-4 py-3 text-right">Agent cost</th>
                      <th className="px-4 py-3 text-right">Bookings</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.packages.map((p) => (
                      <tr key={p.id} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`admin-package-row-${p.id}`}>
                        <td className="px-4 py-3">
                          <div className="text-stone-900 truncate max-w-[280px]">{p.title}{p.is_featured ? " ★" : ""}</div>
                          <div className="text-xs text-stone-500 font-mono">{p.slug}</div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-stone-700">{p.destination?.name || "—"}</div>
                          <div className="text-[10px] uppercase tracking-widest text-stone-400">{p.destination?.scope}</div>
                        </td>
                        <td className="px-4 py-3"><Badge className={STATUS_TONES[p.status]}>{p.status}</Badge></td>
                        <td className="px-4 py-3 text-right font-mono">{formatPHP(p.guest_price)}</td>
                        <td className="px-4 py-3 text-right font-mono text-stone-600">{formatPHP(p.agent_cost)}</td>
                        <td className="px-4 py-3 text-right">{p.booking_count}</td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex justify-end gap-2">
                            <Button asChild size="sm" variant="outline" data-testid={`admin-package-edit-${p.id}`}>
                              <Link to={`/admin/packages/${p.id}`}><FileEdit size={12} className="mr-1" />Edit</Link>
                            </Button>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button size="sm" variant="ghost" data-testid={`admin-package-menu-${p.id}`}>
                                  <MoreHorizontal size={16} />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                {p.status !== "published" ? (
                                  <DropdownMenuItem onClick={() => changeStatus(p.id, "published")} data-testid={`admin-package-publish-${p.id}`}>
                                    <Send size={14} className="mr-2" />Publish
                                  </DropdownMenuItem>
                                ) : null}
                                {p.status !== "draft" ? (
                                  <DropdownMenuItem onClick={() => changeStatus(p.id, "draft")}>
                                    <FileEdit size={14} className="mr-2" />Move to draft
                                  </DropdownMenuItem>
                                ) : null}
                                {p.status !== "archived" ? (
                                  <DropdownMenuItem onClick={() => changeStatus(p.id, "archived")}>
                                    <Archive size={14} className="mr-2" />Archive
                                  </DropdownMenuItem>
                                ) : null}
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  className="text-red-600 focus:text-red-700"
                                  onClick={() => remove(p.id, p.title)}
                                  disabled={p.booking_count > 0}
                                  data-testid={`admin-package-delete-${p.id}`}
                                >
                                  Delete
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
            <Alert>
              <AlertDescription className="text-xs">
                Published packages appear on the public website immediately. Archive to hide.
              </AlertDescription>
            </Alert>
          </>
        )}
      </div>
    </AdminShell>
  );
}
