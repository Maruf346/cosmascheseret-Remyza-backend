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

