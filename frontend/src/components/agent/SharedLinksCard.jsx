import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import { copyText, shareUrl } from "@/components/agent/ShareLinkDialog";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Copy, Ban } from "lucide-react";
import { toast } from "sonner";

const TONES = { active: "bg-emerald-100 text-emerald-800", expired: "bg-stone-200 text-stone-600", revoked: "bg-red-100 text-red-700" };
const fmt = (iso) => new Date(iso).toLocaleDateString("en-PH", { month: "short", day: "numeric", year: "numeric" });

export const SharedLinksCard = () => {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["agent-share-links"],
    queryFn: () => api.get("/agent/share-links").then((r) => r.data.links),
  });
  const revoke = async (l) => {
    try {
      await api.post(`/agent/share-links/${l.id}/revoke`);
      toast.success("Link switched off.");
      qc.invalidateQueries({ queryKey: ["agent-share-links"] });
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };
  const rows = data || [];
  return (
    <Card className="border-stone-200 lg:col-span-2" data-testid="shared-links-card">
      <CardHeader>
        <CardTitle className="text-base">Shared links</CardTitle>
        <CardDescription>Quote and receipt links you've sent. Each works for 30 days unless you switch it off.</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {rows.length === 0 ? <p className="px-6 pb-6 text-sm text-stone-500" data-testid="shared-links-empty">No links yet.</p> : rows.map((l) => (
          <div key={l.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-6 py-3 border-t border-stone-100" data-testid={`shared-link-row-${l.id}`}>
            <div className="min-w-0">
              <div className="text-sm font-medium truncate">{l.label}</div>
              <div className="text-xs text-stone-500">
                Sent {fmt(l.created_at)} · {l.status === "active" ? `expires ${fmt(l.expires_at)}` : l.status} · opened {l.open_count}×
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium capitalize ${TONES[l.status]}`} data-testid={`shared-link-status-${l.id}`}>{l.status}</span>
              {l.status === "active" ? (
                <>
                  <Button variant="ghost" size="sm" onClick={() => copyText(shareUrl(l.path))} data-testid={`shared-link-copy-${l.id}`}><Copy size={14} /></Button>
                  <Button variant="ghost" size="sm" onClick={() => revoke(l)} data-testid={`shared-link-revoke-${l.id}`}><Ban size={14} className="mr-1" />Switch off</Button>
                </>
              ) : null}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};
