/**
 * Base URL of the backend.
 *
 * Local dev: REACT_APP_BACKEND_URL=http://localhost:8001 (separate servers).
 * Hosted:    leave it empty — the backend serves this app from the same
 *            address, so the current page's origin is the backend. Built
 *            once, the same bundle works on any domain.
 */
export const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || window.location.origin).replace(/\/$/, "");
