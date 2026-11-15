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
- **2026-10-29 Phase 5** — Agent Portal (markup model; withdrawals CANCELLED by user):
  - Settings `minimum_markup_amount` / `maximum_markup_amount` (fixed PHP per
    pax, defaults 0 / 10,000, min ≤ max enforced, shown in Admin Settings).
  - `agent_package_markups` collection (unique agent_id+package_id).
    Markup status: unset / ok / out_of_range → `bookable` only when ok
    (no markup = can't sell; admin narrowing range flags & blocks).
  - Package `commission_amount` kept as extra bonus on top of markup.
  - `/api/agent/*`: dashboard, packages (+detail, PUT markup), fund-requests
    (bounds, max 5 pending, feeds admin queue), ledger (Date | Booking ID |
    Description | Net Cost | Customer Paid | Earned | Status), transactions,
    profile (phone/address). All audit-logged, agent resolved from JWT.
  - Frontend: AgentShell, Dashboard, Catalog + markup dialog, package
    detail, Top-ups, Ledger (Earnings / Wallet tabs), Profile (+password).
  - "Customer view" privacy toggle (localStorage) masks net cost, markup,
    earnings, balances and top-up amounts; shows retail only.
  - Tests: `tests/test_agent_phase5_portal.py` (24/24).
- **2026-10-29 Phase 6** — Agent customers, bookings & customer quotes:
  - `/api/agent/customers` CRUD (own only; delete blocked if bookings exist).
  - `POST /api/agent/bookings`: requires markup `ok`, pax range, future date;
    atomic overdraft-proof `$inc` debit of NET cost only (BOOKING_DEBIT,
    idempotency `booking_debit:{id}`), snapshot markup/retail on booking,
    status pending until admin confirms. Agents can't cancel (admin only).
  - Bonus commission is only recorded as earnings (ledger), never paid in.
  - Quote PDF (reportlab): `POST /api/agent/quotes/pdf`,
    `GET /api/agent/bookings/{id}/quote.pdf` — brand, agent contact, retail
    per pax + total, inclusions/exclusions, 7-day validity. No net/markup.
  - Admin refund / commission reversal switched to atomic `$inc`.
  - Frontend: Customers, Bookings (tabs), New booking, Booking detail,
    Book/Quote buttons on package detail; Customer view respected.
  - Tests: `tests/test_agent_phase6_bookings.py` (25/25).
- **2026-10-29 Phase 7** — Booking status alerts + customer payment tracking:
  - `notify_agent` (in-portal `notifications`, failure-safe) on admin booking
    confirm/complete/cancel (refund amount in text) and top-up approve/reject.
  - `/api/agent/notifications` list + unread_count, mark one / all read.
  - `booking_payments` collection; agent add/delete payments (no overpay,
    not on cancelled, no future date). `guest_payment_status` derived
    automatically; admin manual override now 409; admin sees payments.
  - Bookings list `balance_due` + `?payment=owing`; dashboard
    `customer_balance_due` / `bookings_owing`.
  - Frontend: bell with unread badge (desktop + mobile), dashboard Alerts
    card + "Customers still owe" card, PaymentsCard on booking detail,
    Balance due tab/column, admin read-only Customer payments dialog.
  - Tests: `tests/test_agent_phase7_alerts_payments.py` (25/25).
- **2026-10-29 Phase 8** — Agent branding, receipts, trip reminders:
  - Emergent object storage (`core/storage.py`, EMERGENT_LLM_KEY +
    APP_STORAGE_PREFIX). Agent logo upload (PNG/JPG ≤2 MB, Pillow-verified),
    served via `GET /api/agent/profile/logo`; soft remove.
  - Agent-edited `business_name` (falls back to admin's agency name).
  - Quotes + new payment receipts (`/bookings/{id}/payments/{pid}/receipt.pdf`)
    are AGENT-BRAND ONLY (logo, business name, contact). Receipt shows this
    payment, history up to it, total, paid to date, balance due. Stable
    receipt numbers via booking `payment_seq` → payment `receipt_seq`.
  - Trip reminders: dashboard `trips_due` (pending/confirmed, travel within
    14 days, balance > 0) + one `booking.payment_due` bell alert per booking
    (partial unique index guarantees one).
  - Frontend: Branding card on Profile, logo/name in sidebar + mobile header,
    Receipt button per payment, Trips-due dashboard card. Query cache cleared
    on login/logout.
  - Tests: `tests/test_agent_phase8_branding_receipts.py` (22/22).
- **2026-10-30 Phase 9** — Brand colour + private share links:
  - `brand_color` (#RRGGBB) on agent profile; used on quote/receipt PDFs and
    portal accents (body.agent-theme CSS remap of teal utilities, auto
    contrast text). Too-light warning in picker.
  - `share_links` collection (token_urlsafe(24), 30-day expiry, revoke).
    Kinds: quote (price snapshot), booking_quote, receipt. Public
    `GET /api/share/{token}` streams PDF inline; 404/410 HTML pages.
    Receipts remain downloadable as files.
  - Frontend: colour picker on Branding card, ShareLinkDialog (Get link /
    Quote link / payment Link), Profile "Shared links" card with switch-off.
  - Tests: phase 9 pytest 13/13, regression 72/72.
- **2026-11-14 Hardening (balance races + lockout)**:
  - Admin balance adjustment and fund-request approval now use atomic
    `$inc` (previously read-modify-`$set`, which could silently overwrite a
    concurrent booking debit). Debits keep an overdraft `$gte` guard.
  - Fund-request approve claims the request atomically (pending→approved)
    before crediting, with rollback on failure; reject returns 409 if it
    lost a race (no stray audit/notification).
  - Login lockout IP now uses the proxy-appended X-Forwarded-For entry
    (`TRUSTED_PROXY_HOPS`, default 1) — spoofed left-most values ignored.
  - `scripts/verify_db.py` also checks approved fund requests ⇔ one TOP_UP.
  - Tests: `tests/test_concurrency_hardening.py`.
- **2026-11-15 Rebrand + portable logo storage**:
  - Platform rebranded Biyahe'Ta Bai → eNaviga (official logo, favicon,
    copy). One-time startup migration renames the `brand` setting if it
    still holds a legacy name. Agent branding untouched (agent-only docs).
  - Agent logos now stored in MongoDB (`stored_files`, path `db:<id>`) so
    uploads work on any host without Emergent credentials. Legacy Emergent
    paths still readable when `EMERGENT_LLM_KEY` is set;
    `STORAGE_BACKEND=emergent` restores the old upload target.

## Backlog
### Next candidates
- Email quotes/booking notifications to customers (not chosen yet).
- Agent notification when admin confirms/cancels a booking.

### CANCELLED — Phase 7 Commission Withdrawals (agents collect markup upfront)

### P2 — Phase 8: Hardening
- Rate limits on `/api/public/contact`, invite endpoints and `/api/share/{token}`.
- Make the agent "max 5 pending top-ups" check atomic (currently count-then-insert).
- Make the customer-payment overpay guard atomic (two simultaneous saves could exceed the total).
- Legacy BTB-DEMO-0001 still shows "paid" with no payment rows (set manually pre-Phase 7).
- Brute-force lockout on `/api/auth/login`.
- Periodic financial reconciliation (`balance == SUM(txn)` per account).
- Note: phase4 step3 admin booking tests assume BTB-DEMO-0001 is confirmed; it is
  currently cancelled in this DB, so those tests need a fresh fixture.
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
