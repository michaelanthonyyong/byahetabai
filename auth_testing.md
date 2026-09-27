# Biyahe'Ta Bai Travel — Auth Testing Playbook (Phase 2)

## Database preconditions
```
mongosh
use test_database
db.users.find({role:"admin"}, {email:1, status:1, display_name:1}).pretty()
# → { email: "yongmichael992@gmail.com", status: "active", display_name: "Michael Yong" }

db.users.getIndexes()             # uniq_email
db.auth_tokens.getIndexes()       # uniq_token_hash + ttl_expires_at (expireAfterSeconds: 0)
db.login_attempts.getIndexes()
```

The seeded admin password hash must start with `$2b$`.

## Backend cURL smoke test (localhost)
```
API=http://localhost:8001/api

# 1. login as admin
curl -c admin.txt -X POST $API/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"yongmichael992@gmail.com","password":"Admin@12345"}'

# 2. session
curl -b admin.txt $API/auth/me                                      # 200

# 3. wrong password
curl -o /dev/null -w "%{http_code}\n" -X POST $API/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"yongmichael992@gmail.com","password":"WRONG"}'   # 401

# 4. protected without cookie
curl -o /dev/null -w "%{http_code}\n" $API/auth/me                  # 401

# 5. invite a new agent
INV=$(curl -b admin.txt -X POST $API/admin/agents \
      -H "Content-Type: application/json" \
      -d '{"email":"qa.agent@example.com","display_name":"QA Agent"}')
TOKEN=$(echo $INV | python3 -c "import sys,json;print(json.load(sys.stdin)['invite_token'])")

# 6. accept invitation
curl -X POST $API/auth/accept-invite \
     -H "Content-Type: application/json" \
     -d "{\"token\":\"$TOKEN\",\"new_password\":\"Agent@Pass1\"}"    # {"email":...}

# 7. login as agent
curl -c agent.txt -X POST $API/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"qa.agent@example.com","password":"Agent@Pass1"}'

# 8. agent hits admin (must 403)
curl -o /dev/null -w "%{http_code}\n" -b agent.txt $API/admin/agents # 403

# 9. change own password
curl -b agent.txt -X POST $API/auth/change-password \
     -H "Content-Type: application/json" \
     -d '{"current_password":"Agent@Pass1","new_password":"Agent@Pass2"}'
```

## Browser flow (data-testids)
- `login-card`, `login-email-input`, `login-password-input`, `login-submit-button`, `login-error`
- `admin-dashboard`, `admin-goto-agents`
- `admin-invite-agent-button`, `admin-invite-agent-dialog`
- `admin-invite-email-input`, `admin-invite-name-input`, `admin-invite-agency-input`, `admin-invite-phone-input`
- `admin-invite-submit-button`, `admin-invite-url`, `admin-invite-copy-button`
- `admin-agent-row-<id>`, `admin-agent-reset-<id>`, `admin-agent-toggle-<id>`, `admin-agent-reset-url-<id>`
- `agent-dashboard`
- `set-password-card`, `set-password-new-input`, `set-password-confirm-input`, `set-password-submit-button`, `set-password-success`, `set-password-error`
- `portal-logout-button`, `portal-current-user`
- `forbidden-page`

## Negative RBAC cases the testing agent must cover
- Agent trying `GET /api/admin/agents` → 403 (not 401).
- Any unauthenticated request to `/api/auth/me`, `/api/admin/*` → 401.
- INVITED agent trying to log in with the *placeholder* hash → 401.
- Same invite token used twice → 400 "already used".
- Reset token expired → 400 "expired".
- Direct navigation to `/admin` when logged in as agent → redirected to `/forbidden`.
- Direct navigation to `/agent` when logged in as admin → redirected to `/forbidden`.

## Brute-force lockout (LOGIN_LOCKOUT_ATTEMPTS=5, window 15min)
- 5 failed logins on the same `ip:email` → next login returns 429.
- Successful login resets the counter.
