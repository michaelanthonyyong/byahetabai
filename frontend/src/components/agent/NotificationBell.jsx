import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/admin";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Bell, CheckCircle2, XCircle, Flag, Wallet } from "lucide-react";

const ICONS = {
  "booking.confirmed": [CheckCircle2, "text-emerald-600"],
  "booking.completed": [Flag, "text-sky-600"],
  "booking.cancelled": [XCircle, "text-red-600"],
  "fund_request.approved": [Wallet, "text-emerald-600"],
  "fund_request.rejected": [Wallet, "text-red-600"],
};

export const useNotifications = () =>
  useQuery({
    queryKey: ["agent-notifications"],
    queryFn: () => api.get("/agent/notifications").then((r) => r.data),
    refetchInterval: 30000,
  });

const linkFor = (n) => (n.ref_type === "booking" ? `/agent/bookings/${n.ref_id}` : n.ref_type === "fund_request" ? "/agent/top-ups" : null);

export const AlertsList = ({ items, onPick, empty = "No alerts yet." }) => {
  if (!items.length) return <div className="px-4 py-6 text-sm text-stone-500 text-center" data-testid="alerts-empty">{empty}</div>;
  return items.map((n) => {
    const [Icon, tone] = ICONS[n.kind] || [Bell, "text-stone-500"];
    return (
      <button key={n.id} onClick={() => onPick(n)} data-testid={`alert-item-${n.id}`}
        className={`w-full text-left flex gap-3 px-4 py-3 border-b border-stone-100 last:border-0 transition-colors hover:bg-stone-50 ${n.is_read ? "" : "bg-teal-50/60"}`}>
        <Icon size={16} className={`mt-0.5 shrink-0 ${tone}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-stone-900">{n.title}</span>
            {!n.is_read ? <span className="h-2 w-2 rounded-full bg-teal-600 shrink-0" data-testid={`alert-unread-${n.id}`} /> : null}
          </div>
          <div className="text-xs text-stone-600 mt-0.5">{n.body}</div>
          <div className="text-[11px] text-stone-400 mt-1">{timeAgo(n.created_at)}</div>
        </div>
      </button>
    );
  });
};

export const useOpenAlert = () => {
  const nav = useNavigate();
  const qc = useQueryClient();
  return async (n) => {
    if (!n.is_read) {
      await api.post(`/agent/notifications/${n.id}/read`);
      qc.invalidateQueries({ queryKey: ["agent-notifications"] });
    }
    const to = linkFor(n);
    if (to) nav(to);
  };
};

export const NotificationBell = ({ testid = "notification-bell" }) => {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const { data } = useNotifications();
  const openAlert = useOpenAlert();
  const unread = data?.unread_count || 0;
  const readAll = async () => {
    await api.post("/agent/notifications/read-all");
    qc.invalidateQueries({ queryKey: ["agent-notifications"] });
  };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button className="relative rounded-full border border-stone-300 bg-white p-2 text-stone-700 hover:border-stone-400 transition-colors" data-testid={testid} aria-label="Alerts">
          <Bell size={16} />
          {unread ? (
            <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] rounded-full bg-red-600 px-1 text-[10px] font-semibold leading-[18px] text-white text-center" data-testid={`${testid}-count`}>
              {unread > 9 ? "9+" : unread}
            </span>
          ) : null}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0" data-testid="notification-panel">
        <div className="flex items-center justify-between px-4 py-3 border-b border-stone-200">
          <span className="font-medium text-sm">Alerts</span>
          {unread ? <button onClick={readAll} className="text-xs text-teal-800 hover:underline" data-testid="notification-read-all">Mark all read</button> : null}
        </div>
        <div className="max-h-96 overflow-y-auto">
          <AlertsList items={data?.notifications || []} onPick={(n) => { setOpen(false); openAlert(n); }} />
        </div>
      </PopoverContent>
    </Popover>
  );
};
