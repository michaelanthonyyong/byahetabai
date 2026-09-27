import { formatPHP } from "@/lib/money";

/** Format an ISO timestamp as a relative label ("3m ago", "yesterday"). */
export function timeAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const s = Math.round(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function humanAction(a) {
  const map = {
    "agent.invite": "Invited agent",
    "agent.status_change": "Changed agent status",
    "agent.update": "Updated agent",
    "agent.adjust_balance.credit": "Credited agent balance",
    "agent.adjust_balance.debit": "Debited agent balance",
    "agent.password_set_directly": "Set agent password directly",
    "agent.password_reset_token_issued": "Issued reset link for agent",
    "fund_request.approve": "Approved fund request",
    "fund_request.reject": "Rejected fund request",
    "fund_request.create_on_behalf": "Filed fund request on behalf of agent",
    "booking.create": "Created booking",
    "booking.confirm": "Confirmed booking",
    "settings.update": "Updated system setting",
    "contact.update": "Updated contact message",
    "package.create": "Created package",
    "package.update": "Updated package",
    "package.delete": "Deleted package",
    "destination.create": "Created destination",
    "destination.update": "Updated destination",
    "destination.delete": "Deleted destination",
  };
  return map[a] || a;
}

export { formatPHP };
