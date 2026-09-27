# Biyahe'Ta Bai Travel — PRD

## Original problem statement
Production-oriented B2B travel booking portal with three experiences: Public
website, Agent Portal, and Master Admin Portal. Strict financial integrity
(booking + commission balances never merged), atomic balance-changing ops
paired with audit logs, strong RBAC (agent isolation), custom JWT auth via
httpOnly cookies with invite-only agent onboarding. Public site mirrors
biyahetabaitravel.com.

## Personas
- **Public visitor** — browses destinations & packages, submits contact form.
- **Agent** — logs in, sees agent_cost + commission, manages own customers +
  bookings, submits fund top-ups and commission withdrawals. (Portal in
  Phase 5+.)
- **Master Admin** — invites/manages agents, curates catalog, approves
  bookings/fund requests/withdrawals, monitors financial invariants, edits
  system settings, reads full audit log.

## Core requirements
- Custom JWT auth via httpOnly cookies; agents are invite-only.
- Agent isolation — `agent_id` always derived from JWT, never trusted.
- Ledger-first finance — `financial_transactions` append-only; balances are
  aggregations. Every mutation writes a transaction *and* an audit log.
- Idempotency keys on approval-driven writes so retries can't double-credit.

## Implemented (chronological)
- **2026-02 Phase 1** — DB architecture, models, seed & verify scripts.
- **2026-02 Phase 2** — JWT auth, RBAC, invite/reset flows, httpOnly cookies.
- **2026-02 Phase 3** — Public marketing site driven by `/api/public/*`.
- **2026-02 Phase 4 Step 1** — Admin Dashboard + Agents + ledger-based
  balance adjustment.
- **2026-02 Phase 4 Step 2** — Admin Packages/Destinations CRUD with
  publishing rules.
- **2026-02 Phase 4 Step 3** — Admin Bookings + state machine + refunds +
  commission reversal.
- **2026-02 Phase 4 Step 4** — Admin Fund Requests. Atomic approve with
  `idempotency_key=fund_request:{id}` + self-heal on partial writes.
  Amount bounds sourced from settings.
- **2026-02 Phase 4 Step 5** — Remaining Admin surfaces:
  - **Transactions** (`/api/admin/transactions`, `/export.csv`) — global
    ledger with agent/account/type/date filters and CSV export.
  - **Contact Messages** (`/api/admin/contacts`) — status inbox
    (new→read→responded→archived), internal notes, auto-flip new→read on
    first open, audit-logged updates.
  - **Settings** (`/api/admin/settings`) — controlled schema editor for
    `brand`, `minimum_topup_amount`, `maximum_topup_amount`,
    `commission_withdrawals_enabled`. Cross-key rule keeps min ≤ max.
    Every change audit-logged. Fund-request bounds read live from settings.
  - **Audit Log** (`/api/admin/audit-logs`, `/actions`) — global timeline
    with actor lookup and action/entity/target-id/date filters.
  - Frontend: `AdminTransactionsPage`, `AdminContactsPage`,
    `AdminSettingsPage`, `AdminAuditLogsPage`. Sidebar has no SOON items.
  - Tests: `tests/test_admin_phase4_step5.py` (46/46 passing).

## Backlog
### P0 — Phase 5: Agent Portal (Read-only + Fund Requests)
- Agent portal shell + role-based routing.
- Agent dashboard: balances, recent bookings.
- Catalog view showing agent_cost + commission (no guest-price emphasis).
- Agent profile page.
- Agent-side `POST /api/agent/fund-requests` submission form (feeds the
  existing admin queue built in Step 4).

### P0 — Phase 6: Agent Customers & Bookings
- Agent CRUD for own customers (strict `agent_id` from JWT).
- Booking creation → atomic `BOOKING_DEBIT`.

### P1 — Phase 7: Commissions & Withdrawals
- Commission accrual visibility.
- Withdrawal request submission (gated by `commission_withdrawals_enabled`).
- Admin Withdrawal queue (mirror of Fund Requests, commission-account debits).

### P2 — Phase 8: Hardening
- Rate limits on `/api/public/contact` and invite endpoints.
- Brute-force lockout on `/api/auth/login`.
- Periodic financial reconciliation (`balance == SUM(txn)` per account).
- Consider Mongo transactions when a replica set is available.

### Deferred UX polish
- Debounced search on admin tables.
- Inline min/max validation on the "New fund request" amount input.
- Character counters on long-form admin fields.
- Admin pages: auto-refresh KPI counts every 30s.

## Key files
- `/app/backend/core/financial_service.py` — all balance mutations.
- `/app/backend/core/settings_service.py` — controlled settings schema.
- `/app/backend/routers/admin_transactions.py`, `admin_contacts.py`,
  `admin_settings.py`, `admin_audit_logs.py`, `admin_fund_requests.py`.
- `/app/frontend/src/pages/admin/*` — one page per admin surface.
- `/app/memory/ARCHITECTURE.md` — schema/ambiguity notes.
- `/app/memory/test_credentials.md` — active test accounts.

## Health
- Broken: none.
- Mocked: none.
