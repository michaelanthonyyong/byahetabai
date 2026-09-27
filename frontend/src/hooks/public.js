import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

async function fetchJSON(path, params) {
  const { data } = await api.get(path, { params });
  return data;
}

export function useBrand() {
  return useQuery({
    queryKey: ["brand"],
    queryFn: () => fetchJSON("/public/brand").then((d) => d.brand),
    staleTime: 5 * 60_000,
  });
}

export function useDestinations({ featured } = {}) {
  return useQuery({
    queryKey: ["destinations", { featured }],
    queryFn: () =>
      fetchJSON("/public/destinations", featured != null ? { featured } : undefined).then(
        (d) => d.destinations,
      ),
  });
}

export function useDestination(slug) {
  return useQuery({
    enabled: !!slug,
    queryKey: ["destination", slug],
    queryFn: () => fetchJSON(`/public/destinations/${slug}`),
  });
}

export function usePackages(filters = {}) {
  const clean = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  );
  return useQuery({
    queryKey: ["packages", clean],
    queryFn: () => fetchJSON("/public/packages", clean),
  });
}

export function usePackage(slug) {
  return useQuery({
    enabled: !!slug,
    queryKey: ["package", slug],
    queryFn: () => fetchJSON(`/public/packages/${slug}`).then((d) => d.package),
  });
}
