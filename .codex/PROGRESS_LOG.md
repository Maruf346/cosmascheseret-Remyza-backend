# PROGRESS LOG

## 2026-08-30

Initial `.codex` project context created.

Recorded:

- Approved Sent.dm workflow.
- Free user and paid user flow.
- Sender Profile architecture.
- 10DLC timing and compliance rules.
- WhatsApp 24-hour customer-service window decision.
- STOP/HELP handling.
- Async webhook requirement.
- Webhook signature verification requirement.
- Sandbox testing limits.
- Separate Sent.dm implementation plan.

Current build direction:

- Keep Twilio untouched.
- Add Sent.dm integration in parallel.
- Start in sandbox mode.
- Move to controlled live pilot only after sandbox/API/webhook flow is verified.

Next likely work:

1. Add Sent.dm env placeholders.
2. Create `sentdm` Django app.
3. Add Sent.dm client wrapper.
4. Add account/profile/message sandbox endpoints.
5. Add webhook event model and raw webhook logger.
6. Add signature verification.
7. Add async processing/task boundary.


## 2026-08-30 - SENT.DM SANDBOX IMPLEMENTATION SLICE

Completed:

- Added isolated `sentdm` Django app while leaving all existing Twilio code untouched.
- Added Sent.dm configuration placeholders in `.env.example`: API base, API key, optional organization ID, sandbox mode, webhook secret, and webhook tolerance.
- Removed `SENTDM_ACCOUNT_ID` from the plan because the backend does not need it for current API calls.
- Wired Sent.dm URLs under `/api/v1/sentdm/`.
- Added Swagger/OpenAPI grouping under the `Sent.dm` tag.
- Added models and migration for `SentDMProfile`, `SentDMMessage`, and `SentDMWebhookEvent`.
- Added Sent.dm client wrapper for account checks, profile list/create/complete, campaign create, and message send.
- Added sandbox send endpoint with guardrail: it refuses to run when `SENTDM_SANDBOX_MODE=False`.
- Added webhook event capture and HMAC-SHA256 signature verification helper.
- Added initial tests for sandbox payload switching, webhook signature validation, and profile status normalization.

Validation run:

- `python manage.py makemigrations sentdm` passed and created `sentdm/migrations/0001_initial.py`.
- `python manage.py check` passed.
- `python -m compileall -q sentdm cheshara_config core` passed.
- `python manage.py test sentdm` passed with 6 tests.
- `python manage.py spectacular --file tmp_schema.yml --validate` completed successfully; Sent.dm serializer discovery issues were fixed, while older unrelated schema warnings/errors remain in existing apps.

Notes:

- No real Sent.dm API key or webhook secret was committed.
- `SENTDM_ORGANIZATION_ID` is optional for now and should only be used later as a live-mode safety check against `GET /v3/me`.
- The next implementation step should add the async processing boundary for inbound webhooks, then map STOP/HELP handling into the lead/conversation workflow.

## 2026-08-30 - DORMANT SENT.DM LIVE SEND PATH

Completed:

- Added shared Sent.dm message send service used by both sandbox and future live sending.
- Added `send_live_message()` service wrapper for production sends.
- Added `SentDMSendMessageAPIView` for future live outbound sending.
- Kept the live route commented in `sentdm/urls.py` with an activation note.
- Preserved the active sandbox route for current testing.
- Added guardrails so sandbox and live endpoints reject the wrong `SENTDM_SANDBOX_MODE`.
- Added tests for sandbox/live mode guards and message status normalization.

Validation run:

- `python manage.py check` passed.
- `python manage.py test sentdm` passed with 9 tests.
- `python -m compileall -q sentdm` passed.

Decision:

- Production live send is code-ready but intentionally disabled at URL level until live Sent.dm credentials, approved Sender Profiles, webhook secret, async inbound flow, and real lead/conversation routing are ready.
