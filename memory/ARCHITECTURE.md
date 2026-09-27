# Biyahe'Ta Bai Travel — Architecture Analysis (V1)

> Status: Planning artifact only. No feature code will be written until phased implementation is approved.

## 1. Recommended Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | React 19 + React Router 7 + Tailwind + shadcn/ui | Matches existing scaffold |
| Data fetching | TanStack Query | Cache invalidation for balance/booking screens |
| Forms/validation | react-hook-form + zod | Strong client-side contracts on financial forms |
| Backend | FastAPI + Motor (async MongoDB) | Matches scaffold |
| Auth | JWT (HS256) + bcrypt | Custom auth (no public registration) |
| DB | MongoDB replica set | Financial atomicity requires transactions |
| Money | Decimal128 (or int centavos) | Never float for money |
| Testing | pytest + testing_agent | Scaffolded |

Currency: PHP only in V1.

## 2. Application Architecture

Single React SPA with three experiences (`/`, `/agent/*`, `/admin/*`) separated by route prefix + RBAC guards. Single FastAPI app with `router → service → repository` separation so financial logic is isolated and testable.

## 3. Frontend Architecture

```
frontend/src/
├── App.js
├── lib/{api,auth,money,queryClient}.js
├── contexts/AuthContext.jsx
├── components/{ui,shared,public,agent,admin}
├── pages/{public,auth,agent,admin}
├── hooks/
└── routes/{PublicRoutes,AgentRoutes,AdminRoutes}.jsx
```

Shared package presentational components (`PackageCard`, `PackageDetailBlock`) are reused by public site and Agent Portal.

## 4. Backend Architecture

```
backend/
├── server.py
├── core/{config,security,deps,db,errors,audit}.py
├── models/           # Pydantic BaseDocument, PyObjectId
├── repositories/     # Thin DB access, no business logic
├── services/         # Business rules — ONLY place balances change
├── routers/{public,auth,agent,admin}.py
└── seed.py           # Idempotent
```

Balances mutate only in `services/*`, only inside Mongo transactions that also write `transactions` + `audit_logs`.

## 5. Database Architecture

- Single DB, replica set for ACID transactions. Fallback: outbox pattern with unique `ref_id` guard.
- Monetary fields: Decimal128. Timestamps: BSON dates (align with scaffold).
- `id` is UUID string; `_id` never exposed.

### Collections
users, agents, destinations, packages, customers, bookings, transactions, fund_requests, commission_withdrawals, audit_logs, settings.

## 6. Complete Database ERD

```
users 1─1 agents ──owns──▶ customers
                    │
                    ├──▶ bookings ──▶ packages ──▶ destinations
                    │
                    ├──▶ fund_requests ──▶ transactions
                    │
                    └──▶ commission_withdrawals ──▶ transactions

audit_logs ← every admin-mutation
settings   ← feature flags
```

### Enums

- users.role: admin | agent
- users.status / agents.status: active | disabled | invited
- packages.scope: domestic | international
- packages.status: draft | published | archived
- bookings.status: pending | confirmed | cancelled | completed
- bookings.guest_payment_status: unpaid | partial | paid (info only)
- transactions.type: TOP_UP | BOOKING_DEBIT | BOOKING_REFUND | COMMISSION_ACCRUAL | COMMISSION_WITHDRAWAL | ADJUSTMENT_DEBIT | ADJUSTMENT_CREDIT
- fund_requests.status / commission_withdrawals.status: pending | approved | rejected

### Indexes

- users.email unique
- packages.status + scope + destination_id
- bookings.agent_id + created_at desc
- customers.agent_id + name
- transactions.agent_id + created_at desc, transactions.ref_id
- fund_requests.status + created_at
- audit_logs.target_type + target_id, audit_logs.created_at desc

## 7. Authentication Architecture

- No public agent registration; admin creates or invites.
- bcrypt (cost 12); JWT HS256; short access TTL + refresh token.
- Agent JWT `sub` derives `agent_id` server-side; body/query `agent_id` never trusted.
- Password reset by admin in V1; self-service reset requires email integration (Ambiguity A7).
- Brute-force lockout on `/api/auth/login`.
- Auth implementation MUST go through `integration_playbook_expert_v2` before code is written.

## 8. RBAC Architecture

Two roles: admin, agent.
- Route guard: FastAPI dep `require_role(...)`.
- Data guard: every agent-scoped repo filter injects `agent_id` from JWT.
- Cross-agent ID access returns 404 (not 403) to prevent enumeration.
- Agents cannot hit balance-mutating endpoints directly. Approvers cannot be the requester (asserted in service).

## 9. API Structure

All under `/api`.

- Public: `/api/public/{destinations,packages,contact}`
- Auth: `/api/auth/{login,refresh,logout,me}`
- Agent: `/api/agent/{dashboard,packages,customers,bookings,balance,transactions,fund-requests,commissions,profile}`
- Admin: `/api/admin/{agents,packages,destinations,bookings,fund-requests,commission-withdrawals,transactions,audit-logs,settings}`

Public endpoints expose only whitelisted package fields (no `agent_cost`, no `commission`).

## 10. Financial Transaction Architecture

### Invariants
1. `transactions` is append-only.
2. `agents.booking_balance == SUM(signed txn.amount where type ∈ booking-balance types)`. Same for commission.
3. Every balance change is one Mongo transaction: entity + balance + transactions + audit_logs.
4. Approval endpoints accept `Idempotency-Key`.
5. `transactions.amount` is signed.

### Three separate streams (never merged)
- **Agent Booking Balance**: TOP_UP, BOOKING_DEBIT, BOOKING_REFUND, ADJUSTMENT_*.
- **Guest Payment**: `bookings.guest_payment_status` only; no ledger impact.
- **Agent Commission**: COMMISSION_ACCRUAL, COMMISSION_WITHDRAWAL.

### Booking creation (atomic)
Validate balance ≥ cost → insert booking → decrement balance → insert BOOKING_DEBIT txn → audit.

### Fund request approval (atomic)
Assert pending → mark approved → increment balance → insert TOP_UP txn → audit. `decided_by != agent_id`.

### Commission accrual
Proposed default: on booking status → confirmed (accrual = commission × pax). Trigger and formula pending Ambiguity A2/A3.

### Cancellation/refund
Proposed: BOOKING_REFUND offset + reversing COMMISSION_ACCRUAL if accrued. Pending A4.

## 11. Folder/Project Structure

```
/app
├── backend/
├── frontend/
├── memory/{ARCHITECTURE.md, PRD.md, test_credentials.md}
├── tests/
└── test_reports/
```

## 12. Shared UI / Component Architecture

- shadcn primitives from `components/ui/*`
- `components/shared/*`: BrandHeader, BrandFooter, Money, StatusBadge, EmptyState, DataTable
- `components/public/*`: PackageCard, PackageDetailBlock, DestinationCard, Hero — reused by Agent Portal
- `components/agent/*` and `components/admin/*`: role-specific dashboards and forms
- Design tokens in CSS vars; no purple/violet; imagery-forward Philippine palette

## 13. Public Website Architecture

Routes: `/`, `/destinations`, `/destinations/:slug`, `/packages`, `/packages/:slug`, `/about`, `/contact`.
Data via `/api/public/*`. Only `packages.status=published` shown. No agent-cost/commission exposure.

## 14. Agent Portal Architecture

Routes under `/agent/*` guarded by `RequireRole('agent')`:
Dashboard, Packages (with agent_cost + margin), Customers, Bookings, Balance + ledger, Commissions, Profile.
Server-side pagination and agent-scoped filters everywhere.

## 15. Admin Portal Architecture

Routes under `/admin/*` guarded by `RequireRole('admin')`:
Dashboard, Agents, Packages, Destinations, Bookings, Approvals inbox (fund requests + withdrawals), Transactions, Audit Logs, Settings.

## 16. Recommended Development Phases

- **Phase 0** Foundations: env, tokens, BaseDocument, Mongo txn helper, JWT/bcrypt scaffold, seed script.
- **Phase 1** Public Website: destinations, packages, package detail, home, about, contact.
- **Phase 2** Admin catalog: login, destinations/packages CRUD, draft/publish, audit.
- **Phase 3** Admin agent mgmt: create/invite/disable, reset password, manual balance adjustment.
- **Phase 4** Agent portal read-only: login, dashboard, view packages/balance/profile.
- **Phase 5** Booking balance & fund requests: agent submit → admin approve (TOP_UP atomic).
- **Phase 6** Customers & bookings: CRUD customers, create booking (BOOKING_DEBIT atomic), admin cancel/refund.
- **Phase 7** Commissions: accrual on confirmed booking, withdrawal request, admin approval.
- **Phase 8** Hardening: reconciliation job, rate limits, lockout, end-to-end tests.

Each phase leaves the app runnable and is verified before the next.

## 17. Testing Strategy

- pytest unit tests for services (atomicity, isolation, invariants).
- RBAC integration tests: agent A cannot access agent B's data via any path.
- Financial invariants: SUM(txn.amount) == stored balance across random operation sequences.
- E2E via testing_agent at end of each phase.
- Negative tests on admin endpoints from agent role.

## 18. Security Strategy

- bcrypt, no plaintext, no password logging.
- Short JWT TTL, secret from env, HS256.
- No public registration.
- All balance mutations server-side, in transactions, audited.
- Agent-scoped queries enforced in repository layer.
- 404 (not 403) on cross-agent access.
- Rate limits on `/api/public/contact` and `/api/auth/login`.
- CORS env-driven; HTTPS via ingress.
- Decimal128 for money.
- Idempotency-Key on approvals.
- Audit log with actor_id, actor_role, before/after, ip, ua.

## 19. Biyahe'Ta Bai Visual/UX Reference Handling

No URL/screenshots supplied in this task. Options:
1. User provides URL/screenshots → passed to `design_agent_full_stack`.
2. Proceed with an on-brand tropical Philippine default via `design_agent_full_stack`.

Confirm before Phase 1 UI work.

## 20. Ambiguities Requiring Business Decisions

| # | Topic | Question |
|---|---|---|
| A0 | Brand reference | Provide existing site URL/screenshots or accept default? |
| A1 | Money storage | Decimal128 vs int centavos? |
| A2 | Commission trigger | Confirmed / completed / fully-paid? |
| A3 | Commission source | Per-package fixed / % / global / tier? |
| A4 | Cancellation refund policy | Full / partial+fee / admin-only manual? |
| A5 | Guest payment tracking | Enum only or enum + amount? |
| A6 | Agent creation | Direct password set or email invite? |
| A7 | Password reset | Admin-only or self-serve email? |
| A8 | Commission withdrawals | Default on or off? |
| A9 | Minimum top-up amount | None or threshold? |
| A10 | Overdraft | Never allowed vs admin override? |
| A11 | Multi-currency | PHP only for V1? |
| A12 | Package pricing model | Per-person × pax vs flat? |
| A13 | Booking editing scope | Which fields, until which status? |
| A14 | Timezone | Assume PHT (UTC+8)? |
| A15 | Fund request proof | Required file, optional file, or text ref? |

No business rules will be invented — each is confirmed before the phase that needs it.

## 21. Environment & Infrastructure Notes

- Backend `0.0.0.0:8001`; all APIs `/api/*`; frontend uses `REACT_APP_BACKEND_URL`.
- Mongo replica set required for transactions; verify at Phase 0.
- Phase 0 secrets to add: `JWT_SECRET`, `JWT_ACCESS_TTL_MIN`, `JWT_REFRESH_TTL_DAYS`, `BCRYPT_ROUNDS`.
