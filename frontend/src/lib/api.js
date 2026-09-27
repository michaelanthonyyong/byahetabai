import axios from "axios";

/**
 * Central axios instance for all API calls.
 * - baseURL: REACT_APP_BACKEND_URL from env (never hardcode)
 * - withCredentials: send httpOnly cookies to backend
 * - Uniform error normalisation (FastAPI 422 returns array; render-safe)
 */
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

export function formatApiError(err) {
  const detail = err?.response?.data?.detail;
  if (detail == null) return err?.message || "Something went wrong.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  }
  if (detail?.msg) return detail.msg;
  return String(detail);
}
