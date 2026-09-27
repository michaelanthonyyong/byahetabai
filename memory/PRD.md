# Biyahe'Ta Bai Travel — PRD

## Original problem statement
Production-oriented B2B travel booking portal with three experiences: Public
website, Agent Portal, and Master Admin Portal. Strict financial-transaction
integrity (agent booking balance and commission balance never merged), atomic
balance-changing operations paired with audit logs, strong RBAC (agents can
never read other agents' data), custom JWT auth via httpOnly cookies with
invite-only agent onboarding. Public site must mirror biyahetabaitravel.com.

## Personas
- **Public visitor** — browses destinations & packages, submits contact form.
- **Agent** — logs in, sees agent_cost + commission, manages their own
  customers and bookings, submits fund top-ups and commission withdrawals.
- **Master Admin** — invites/manages agents, curates catalog, approves
  bookings/fund requests/withdrawals, monitors financial invariants.

## Core requirements
- Custom JWT auth via httpOnly cookies; agents are invite-only.
- Agent isolation: `agent_id` is always derived from the JWT, never trusted
  from a request body/query.
- Ledger-first finance: `financial_transactions` append-only; balances are
  aggregations. Every mutation writes a transaction **and** an audit log.
- Idempotency keys on approval-driven writes so retries can't double-credit.

## Implemented (chronological)
- **2026-02-XX Phase 1** — DB architecture, models, seed & verify scripts.
- **2026-02-XX Phase 2** — JWT auth, RBAC, invite/reset flows, httpOnly cookies.
- **2026-02-XX Phase 3** — Public marketing site (home, destinations,
  packages, contact) driven by `/api/public/*`.
- **2026-02-XX Phase 4 Step 1** — Admin Dashboard + Agent management +
  ledger-based balance adjustment.
- **2026-02-XX Phase 4 Step 2** — Admin Packages / Destinations CRUD with
  publish/archive rules.
- **2026-02-XX Phase 4 Step 3** — Admin Bookings + state machine +
  refunds + commission reversal.
- **2026-02-XX Phase 4 Step 4** — Admin Fund Requests. `/api/admin/fund-requests`
  (list, detail, create-on-behalf, approve, reject). Approve is atomic:
  writes TOP_UP ledger row with `idempotency_key=fund_request:{id}`,
  credits booking_balance, flips request status, writes audit log. Self-heals
  partial writes on retry. Reject requires ≥3-char reason.
  Frontend: `/admin/fund-requests` with status tabs, approve/reject dialogs,
  create-on-behalf dialog with agent picker. Dashboard KPI links here.
  Tests: `tests/test_admin_phase4_step4_fund_requests.py` (25/25 passing).

## Backlog
### P0 — Phase 5: Agent Portal (Read-only + Fund Requests)
- Agent portal shell + role-based routing.
- Agent dashboard: balances, recent bookings.
- Catalog view showing agent_cost + commission (no guest price emphasis).
- Agent profile page.
- Agent-side `POST /api/agent/fund-requests` submission form (feeds the
  existing admin queue built in Step 4).

### P0 — Phase 6: Agent Customers & Bookings
- Agent CRUD for own customers (strict `agent_id` from JWT).
- Booking creation → atomic `BOOKING_DEBIT`.

### P1 — Phase 7: Commissions
- Commission accrual visibility + withdrawal requests + admin approvals.

### P2 — Phase 8: Hardening
- Rate limits on `POST /api/public/contact` and admin invite endpoints.
- Brute-force lockout on `/api/auth/login`.
- Periodic financial reconciliation (`balance == SUM(txn)` per account).
- Consider Mongo transactions once a replica set is available (self-heal
  already covers the sandbox case).

### Deferred UX polish
- Debounced search on admin tables.
- Inline min/max validation on the "New fund request" amount input.
- Character counters on long-form admin fields.
- Emit `approved_count`/`rejected_count` alongside `pending_count` so tab
  badges don't need extra queries.

## Key files
- `/app/backend/core/financial_service.py` — all balance mutations.
- `/app/backend/routers/admin_fund_requests.py` — Step 4 queue.
- `/app/backend/seed.py` — idempotent seed.
- `/app/frontend/src/pages/admin/AdminFundRequestsPage.jsx` — admin UI.
- `/app/memory/ARCHITECTURE.md` — schema/ambiguity notes.
- `/app/memory/test_credentials.md` — active test accounts.

## Test credentials
See `/app/memory/test_credentials.md`.

## Health
- Broken: none.
- Mocked: none.
