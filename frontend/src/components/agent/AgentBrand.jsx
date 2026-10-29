import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export const useAgentProfile = () =>
  useQuery({
    queryKey: ["agent-profile"],
    queryFn: () => api.get("/agent/profile").then((r) => r.data.profile),
    staleTime: 60000,
  });

export const logoUrl = (profile) =>
  profile?.has_logo
    ? `${process.env.REACT_APP_BACKEND_URL}/api/agent/profile/logo?v=${encodeURIComponent(profile.logo_updated_at || "")}`
    : null;

export const AgentLogo = ({ profile, className = "h-10 w-10", testid = "agent-brand-logo" }) => {
  const url = logoUrl(profile);
  if (!url) return null;
  return <img src={url} alt={`${profile.brand_name} logo`} className={`${className} object-contain rounded-md bg-white`} data-testid={testid} />;
};
