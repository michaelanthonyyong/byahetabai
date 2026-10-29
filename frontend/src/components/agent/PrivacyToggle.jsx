import { Eye, EyeOff } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { usePrivacy } from "@/contexts/PrivacyContext";

export const PrivacyToggle = ({ testid = "privacy-toggle", compact = false }) => {
  const { hidden, setHidden } = usePrivacy();
  return (
    <label
      className={[
        "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium cursor-pointer transition-colors",
        hidden ? "border-teal-700 bg-teal-700 text-white" : "border-stone-300 bg-white text-stone-700 hover:border-stone-400",
      ].join(" ")}
      title="Hide net cost and markup so customers only see the final price"
    >
      {hidden ? <EyeOff size={14} /> : <Eye size={14} />}
      {compact ? null : <span>{hidden ? "Customer view on" : "Customer view"}</span>}
      <Switch
        checked={hidden}
        onCheckedChange={setHidden}
        data-testid={testid}
        className="data-[state=checked]:bg-teal-500"
      />
    </label>
  );
};

export const Masked = ({ children, testid }) => {
  const { hidden } = usePrivacy();
  if (hidden) {
    return <span data-testid={testid} className="text-stone-400 tracking-widest select-none">••••</span>;
  }
  return <span data-testid={testid}>{children}</span>;
};
