import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Copy, ExternalLink, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { BACKEND_URL } from "@/lib/backendUrl";

export const shareUrl = (path) => `${BACKEND_URL}${path}`;

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success("Link copied.");
  } catch {
    toast.error("Couldn't copy automatically. Select the link and copy it.");
  }
}

const fmt = (iso) => new Date(iso).toLocaleDateString("en-PH", { year: "numeric", month: "short", day: "numeric" });

/** Creates a share link for `body` when opened and shows it with copy/open actions. */
export const ShareLinkDialog = ({ body, onClose }) => {
  const qc = useQueryClient();
  const [link, setLink] = useState(null);
  const [error, setError] = useState(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) {
      return;
    }
    started.current = true;
    api.post("/agent/share-links", body)
      .then((r) => { setLink(r.data.link); qc.invalidateQueries({ queryKey: ["agent-share-links"] }); })
      .catch((err) => setError(formatApiError(err)));
  }, [body, qc]);

  const url = link ? shareUrl(link.path) : "";
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent data-testid="share-link-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Share by link</DialogTitle>
          <DialogDescription>
            Paste this private link into Messenger, Viber or email. It opens the PDF directly and works for 30 days.
          </DialogDescription>
        </DialogHeader>
        {error ? <p className="text-sm text-red-600" data-testid="share-link-error">{error}</p> : !link ? (
          <div className="flex items-center gap-2 text-sm text-stone-500"><Loader2 size={14} className="animate-spin" />Creating link…</div>
        ) : (
          <div className="space-y-2">
            <div className="text-xs text-stone-500">{link.label}</div>
            <div className="flex gap-2">
              <Input readOnly value={url} onFocus={(e) => e.target.select()} data-testid="share-link-url" />
              <Button onClick={() => copyText(url)} className="bg-teal-800 hover:bg-teal-900 shrink-0" data-testid="share-link-copy"><Copy size={14} className="mr-1" />Copy</Button>
            </div>
            <p className="text-xs text-stone-500" data-testid="share-link-expiry">Expires {fmt(link.expires_at)}. Switch it off anytime under Profile → Shared links.</p>
          </div>
        )}
        <DialogFooter>
          {link ? <Button variant="outline" asChild><a href={url} target="_blank" rel="noreferrer" data-testid="share-link-open"><ExternalLink size={14} className="mr-1" />Open</a></Button> : null}
          <Button variant="outline" onClick={onClose} data-testid="share-link-close">Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
