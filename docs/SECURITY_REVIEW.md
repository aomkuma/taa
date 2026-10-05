# Security review before LIVE (TAA-1402)

Date: 2026-10-06. Scope: the engine (Windows, next to MT5), the web service and worker, the PWA, and the
sync between them, with the LIVE path added by TAA-1401. Method: re-check of the threat model (PLAN §A20),
dependency audits, a web checklist (OWASP ASVS L2-lite) and a secrets scan of the repository and its history.
Nothing here replaces the go-live checklist and drills (TAA-1403).

## Result

No blocking finding. Four recommendations for the LIVE machine (below) are operational, not code changes.

## 1. Threat model re-check

| Threat | Mitigation in place | Checked |
|---|---|---|
| A cloud compromise turns risk up or switches LIVE on | Remote commands reduce risk only: `KILL_SWITCH_RELEASE`, `BREAKER_RESET`, `STRATEGY_ENABLE`, `LIMITS_CHANGE`, `RISK_CHANGE`, `MODE_CHANGE`, `CONFIG_CHANGE`, `LIVE_ENABLE` are always rejected (`app/sync/commands.py`, tested). The owner's trading profile can only lower the local `config.yaml` limits (`effective_risk`, §A33). The mode and the LIVE flags exist only in the engine machine's environment. | yes |
| LIVE starts by accident | `build_trading` refuses LIVE without `ENABLE_LIVE_TRADING` and the exact account-bound phrase; the connection needs a REAL account; the six-condition gate runs for every decision and before every `order_send`; the gateway refuses any request whose account does not match the mode (TAA-1401, tested on FakeMT5). | yes |
| A runaway bot | Hard ceilings (3 % per trade), daily/weekly/drawdown limits, breakers, kill switch (file, CLI, PWA), idempotency keys, rate limits, LIVE probation. | yes |
| Close or flatten from a stolen web session | Step-up (fresh TOTP) on the web, plus the engine's own control code (`CONTROL_TOTP_SECRET`, never sent to the cloud). | yes |
| Forged or replayed engine traffic | HMAC-SHA256 over method, path, query, body hash and timestamp; nonce store; skew limit; per-engine keys in the database, revocable. | yes |
| Data tampering after the fact | Hash-chained audit logs (engine and web chains); `app.cli audit verify`. | yes |
| Another user's data (IDOR) | Every engine route resolves only the session user's engines (`OwnedEngine`, 404 otherwise); tests cover every route. | yes |
| Secrets in logs, API or replicas | `SecretStr` everywhere, a log redaction filter, the engine masks secrets in config snapshots, API samples are checked for them. | yes |

## 2. Dependency audits

- Python: `pip-audit` on `requirements.txt` and `requirements/{base,engine,cloud,dev}.txt`: **no known
  vulnerabilities**.
- Frontend: `npm audit` (all and `--omit=dev`): **0 vulnerabilities**.

Run both again before switching LIVE on (`.venv\Scripts\python -m pip_audit -r requirements.txt`,
`npm audit` in `frontend/`).

## 3. Web checklist (ASVS L2-lite)

| Area | State |
|---|---|
| Authentication | argon2id passwords with a policy; TOTP mandatory for every login, single-use time steps; exponential lockout per user and per address; users only via the CLI. |
| Sessions | Server-side sessions; cookie `HttpOnly`, `SameSite=Strict`, `Secure` in production; idle and absolute timeouts; revoke one or all others. |
| CSRF | Every mutation needs the `X-CSRF-Token` header plus an allowed `Origin` (`CsrfSession`); tested (403 without it). |
| Step-up | Control actions need a fresh TOTP (`StepUpSession`). |
| Headers | Strict CSP (no inline script, no CDN), `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, HSTS in production. |
| Input | Pydantic models with `extra="forbid"` and bounds on every body; bounded query parameters; ingest body limits (8 MB compressed, capped decompressed). |
| Errors | One problem shape (`{error: {code, message}}`), no stack traces; OpenAPI and docs off in production. |
| Frontend | Every response validated with zod; secrets (engine keys, TOTP) kept in component state only, never in caches or storage. |

## 4. Secrets scan

- Tracked files: only `.env.example` (placeholders). `.env*`, `data/`, logs and keys are git-ignored.
- Full history (`git log --all -p`): no private keys or API tokens (patterns for PEM keys, GitHub, Anthropic,
  AWS and Slack tokens). The env assignments ever committed are placeholders (`MT5_PASSWORD=change-me`,
  empty secrets, a local SQLite URL).

## 5. Recommendations for the LIVE machine (operational)

1. Keep the MT5 **master password** of the real account in Windows Credential Manager
   (`MT5_PASSWORD=keyring:<service>/<name>`), not as plain text in `.env`.
2. Restrict `.env` and the `data/` folder to the Windows user that runs the engine (no shared or synced
   folders); keep the machine's disk encrypted (BitLocker).
3. Enable two-factor login on the broker's client area, and keep a separate demo login for tests.
4. Rotate `ENGINE_HMAC_SECRET` (PWA → Engines → rotate) and `CONTROL_TOTP_SECRET` before LIVE if they were ever
   shown on a shared screen; both are part of the TAA-1403 drills.
