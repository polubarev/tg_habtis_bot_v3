# Backlog

- user statistics
- reminders
- LLM summary

## Security

Findings from the 2026-08-06 review — details and remediation in
[security_review.md](security_review.md). Suggested order:

- [x] SEC-2 🔴 remove `logger.info(messages)` leaking reflection text to logs
- [x] SEC-1 🔴 stop users binding someone else's sheet in `/config`
- [x] SEC-3 🟠 clear 47 dependency advisories, add `pip-audit` to CI
- [x] SEC-4 🟠 write `expires_at` as a timestamp so a TTL policy can reap sessions
- [x] SEC-5 🟠 rate limit `/reminders/dispatch`
- [ ] SEC-6 🟡 use `hmac.compare_digest` for webhook/dispatch secrets
- [ ] SEC-9 🟡 drop `!src/secrets/*.json` from `.gcloudignore`
- [ ] SEC-10 🟡 delete the dead `src/secrets/` package
- [ ] SEC-7 🟡 idempotency key on habit confirm to close the read-then-write race
- [ ] SEC-8 🟡 prompt injection via diary content — monitor
- [ ] unpin ruff (`<0.15`) and clear the ~280 style findings 0.16 flags

### Deployment actions still required
- [ ] apply the Firestore session TTL policy (command in README → Persistence)
- [ ] purge already-captured reflection text from Cloud Logging
- [ ] run `python scripts/audit_sheet_ownership.py` to check for pre-fix hijacks
- [ ] redeploy — none of the fixes are live until then
