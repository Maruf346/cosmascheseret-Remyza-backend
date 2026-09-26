# CHESERA REMAINING WORK

This file tracks the live checklist for finishing the Chesera Sent.dm migration and production rollout.

Update this file whenever an item is started, completed, deferred, or replaced by a better approach.

Status legend:

- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete
- `[!]` Blocked / waiting on external input

## 1. PRODUCTION SENT.DM VALIDATION

- [ ] Confirm production Sent.dm API key is configured in deployed environment and matches the intended organization account.
- [x] Confirm connected Sent.dm account details through MCP: organization `Chesera LLC`, id `80c15901-8bd6-407f-b623-0958c0374a98`.
- [~] Confirm the production key has admin access required for Sender Profile creation and profile completion. MCP confirms organization identity but does not expose profile-create/admin-role verification; verify with live REST create/complete test.
- [ ] Confirm `SENTDM_SANDBOX_MODE=False` only when ready for controlled live testing.
- [ ] Run one controlled live Sender Profile creation test.
- [ ] Run one controlled live 10DLC campaign submission test.
- [ ] Confirm real Sent.dm number assignment/status behavior.
- [~] Confirm optional WhatsApp/WABA behavior with real credentials. Code now allows inherited organization WABA for provider profile creation without activating agent WhatsApp locally; live validation still needs one real direct-WABA connection test.

## 2. SENT.DM WEBHOOK SETUP

- [ ] Get the production Sent.dm webhook secret from Sent.dm dashboard/API.
- [ ] Configure `SENTDM_WEBHOOK_SECRET` in deployed environment.
- [ ] Register central webhook URL in Sent.dm:

```text
https://api.trychesera.com/api/v1/sentdm/webhooks/inbound/
```

- [ ] Subscribe webhook to inbound message/conversation events.
- [ ] Subscribe webhook to delivery/status events if supported and useful.
- [ ] Subscribe webhook to Sender Profile status events if supported and useful.
- [ ] Confirm Sent.dm can reach the HTTPS webhook URL.
- [ ] Confirm webhook signature verification passes with real Sent.dm headers.
- [ ] Confirm invalid/stale signatures are rejected.

## 3. ASYNC WEBHOOK PROCESSING

- [x] Decide production async worker approach: Celery + Redis.
- [x] Add webhook flow:

```text
verify signature -> store event -> enqueue processing -> return 200 immediately
```

- [~] Add idempotency/deduplication using a payload-derived key, not `X-Webhook-ID` because Sent documents that header as the webhook configuration ID. Task now skips already processed events; provider payload-level duplicate keys still need validation from real webhook examples.
- [x] Add retry-safe processing status on webhook events.
- [x] Add error logging for failed background processing.
- [~] Add tests for duplicate webhook events. Added already-processed task skip test; add duplicate real-payload tests after capturing real event IDs.
- [x] Add tests to prove webhook returns quickly without waiting for AI/OpenAI.

## 4. INBOUND MESSAGE ROUTING

- [ ] Parse real Sent.dm inbound message payload shape from production/sandbox webhook examples.
- [x] Extract Sender Profile ID from webhook payload.
- [x] Match Sender Profile ID to `SentDMProfile`.
- [x] Match `SentDMProfile` to organization and agent/user.
- [x] Store inbound message in `SentDMMessage`.
- [x] Store channel: `sms`, `rcs`, or `whatsapp`.
- [x] Store sender/recipient numbers or contact identifiers.
- [~] Handle payloads where profile/contact/conversation identifiers are missing or differently named. Flexible parser added; still needs real captured payload validation.
- [~] Add tests using real captured webhook payload examples. Tests added with Sent-style sample payload; replace/extend with captured production payloads later.

## 5. CRM LEAD AND CONVERSATION MAPPING

- [x] Decide source of truth for matching inbound contact to lead: Sender Profile + inbound phone number for now; Sent.dm contact/conversation IDs can be added after real payload capture.
- [x] Create or update `crm.Lead` from inbound message when needed.
- [x] Link inbound `SentDMMessage` to lead.
- [x] Create or update `communications.Conversation`.
- [x] Link message history to the conversation.
- [x] Preserve channel history per conversation.
- [x] Add tests for new lead creation from inbound messages.
- [x] Add tests for existing lead/conversation continuation.

## 6. STOP, HELP, AND CONSENT HANDLING

- [x] Add persistent lead opt-out field or confirm existing model field can be reused.
- [x] Detect opt-out keywords before AI processing:

```text
STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT
```

- [x] Mark lead permanently opted out.
- [x] Close/stop active conversations for opted-out lead.
- [x] Prevent future AI replies to opted-out lead.
- [x] Prevent follow-up sequences/reminders to opted-out lead.
- [x] Reply to `HELP` with agent support email/help response.
- [x] Add tests for STOP/HELP before AI generation.
- [x] Add tests that follow-ups cannot send after opt-out.

## 7. AI REPLY INTEGRATION

- [x] Build service boundary for inbound AI reply generation inside `process_sentdm_webhook_event(event)`.
- [x] Connect inbound Sent.dm message to the existing AI reply service.
- [~] Ensure AI uses organization/agent business settings. Current flow uses the existing shared AI service; next prompt-hardening pass should inject business name/use-case constraints.
- [x] Send AI reply through Sent.dm using the correct Sender Profile.
- [x] Store outbound AI reply in `SentDMMessage`.
- [x] Store outbound AI reply in conversation history.
- [x] Disable AI for HOT leads after reply so a human can take over.
- [x] Add tests for AI reply service with mocked OpenAI and mocked Sent.dm client.

## 8. AI COMPLIANCE RULES

- [x] Update AI prompts to enforce Sent.dm/10DLC compliance.
- [x] First message must identify business name.
- [x] First message must include STOP opt-out language.
- [x] Avoid urgency/pressure wording.
- [x] Avoid ALL CAPS.
- [x] Avoid excessive punctuation.
- [x] Avoid link shorteners.
- [x] Stay inside approved use case/vertical.
- [x] Add tests or prompt snapshots for compliance-critical instructions.

## 9. OUTBOUND SEND RULES

- [x] Confirm final channel-selection behavior for `auto`, `sms`, `rcs`, and `whatsapp` in the shared Sent.dm service policy.
- [x] Keep WhatsApp optional; do not block SMS/RCS when WhatsApp is missing.
- [x] For explicit `channel=whatsapp`, require an active direct agent-owned WhatsApp connection, not merely an inherited organization WABA.
- [~] Route scheduled follow-ups outside Meta's 24-hour WhatsApp window to SMS. Shared channel policy is implemented and tested; the existing follow-up task currently sends push reminders, not outbound lead messages.
- [x] Track/check the active WhatsApp customer-service window using `Lead.last_incoming_at`.
- [x] Add tests for WhatsApp 24-hour window routing.
- [ ] Build actual scheduled outbound follow-up message sending if product scope requires Day 1/3/7/14 texts instead of agent push reminders. Use templates for first outbound/new-contact messages; free-form text is safest for inbound/reply conversations only.

## 10. ACTIVATION STATUS SYNC

- [x] Store and return Sender Profile status from Sent.dm in `/api/v1/me/plan-and-progress/`.
- [x] Store and return 10DLC campaign status from Sent.dm in `/api/v1/me/plan-and-progress/`.
- [x] Store and return number assignment status from Sent.dm profile data in `/api/v1/me/plan-and-progress/`: `pending`, `assigned`, or `needs_attention`.
- [x] Store WhatsApp active/not connected state locally on `SentDMProfile`; frontend display wiring remains in the mobile/UI checklist.
- [x] Update `/api/v1/me/plan-and-progress/` with backend activation status values for subscription, compliance, profile, number, campaign, SMS/RCS, and WhatsApp.
- [x] Add dashboard-ready messages:

```text
Messaging activation in progress, usually 1-3 business days.
Messaging active.
Messaging activation needs attention.
Messaging activation is in progress. Number assignment may take additional time if local inventory is unavailable.
```

- [x] Add tests for plan/progress status transitions.

## 11. FRONTEND / MOBILE INTEGRATION

- [ ] Wire signup endpoint `POST /api/v1/client/auth/signup/` before OTP verification for new users.
- [ ] Wire IAP subscription creation/listing endpoints.
- [ ] Wire business compliance form fields.
- [ ] Wire optional WhatsApp connection endpoint and fields:

```text
waba_id
phone_number_id
access_token
```

- [ ] Make WhatsApp clearly optional in the UI.
- [ ] Hide/access-token value after submission.
- [ ] Wire compliance readiness endpoint.
- [ ] Wire Sender Profile create action.
- [ ] Wire campaign create action or replace with backend automation.
- [ ] Wire plan/progress screen.
- [ ] Show clear activation status and missing-field errors.

## 12. PRODUCTION DEPLOYMENT HARDENING

- [ ] Confirm `ALLOWED_HOSTS` includes `api.trychesera.com`.
- [ ] Confirm `CSRF_TRUSTED_ORIGINS` includes `https://api.trychesera.com`.
- [ ] Confirm `SECURE_PROXY_SSL_HEADER` is set correctly behind Nginx.
- [x] Fix Django admin CSS/static routing by removing the Nginx host alias and serving static files through WhiteNoise in the backend container.
- [ ] Confirm SSL renewal works:

```bash
sudo certbot renew --dry-run
```

- [ ] Confirm GitHub Actions deployment is stable.
- [ ] Confirm RDS backups/snapshots are enabled.
- [ ] Confirm server logs are accessible.
- [ ] Confirm error monitoring/log retention plan.
- [x] Fix unrelated CRM migration drift:

```text
crm/migrations/0004_alter_followupreminder_id.py
```

## 13. CLEANUP BEFORE FINAL HANDOFF

- [ ] Update README with final setup/workflow.
- [ ] Update deployment guide after SSL final config is committed.
- [ ] Update Sent.dm workflow docs after live pilot.
- [ ] Confirm Swagger only shows active/current endpoints.
- [ ] Decide whether Twilio endpoints remain hidden or are removed later.
- [ ] Remove stale Twilio-first wording from user-facing docs.
- [ ] Run final test suite.
- [ ] Run final schema validation.
- [ ] Produce final handoff summary for client.

## 14. CRM CONTACTS / LEADS

- [x] Use existing `crm.Lead` as the unified contact/lead record.
- [x] Support manual contact save with full name, phone number, email, business name, and notes.
- [x] Allow contacts before Sent.dm number assignment by making `business_phone` optional.
- [x] Add lead source tracking for manual, CSV upload, and auto-capture.
- [x] Add CSV upload endpoint with duplicate list in the response.
- [x] Add hot/warm/cold lead counts endpoint.
- [x] Add hot/warm/cold lead counts directly to the paginated lead list response.
- [x] Add hot/warm/cold lead list filtering.
- [x] Add lead detail response with activity timeline and conversation messages.
- [x] Add paginated lead conversation endpoint at `/api/v1/leads/{id}/conversation/`.
- [x] Add lead inbox endpoint at `/api/v1/leads/inbox/` with one row per lead and latest message.
- [x] Add metrics: lead score percentage, days in pipeline, total messages, source, and response rate.
- [x] Auto-capture inbound Sent.dm texters as contacts.
- [x] Record key activities: lead created, first reply received, AI welcome/reply sent, and status changed.
- [ ] Frontend/mobile: wire manual contact form.
- [ ] Frontend/mobile: wire CSV upload and duplicate review UI.
- [ ] Frontend/mobile: wire hot/warm/cold counts and filters.
- [ ] Frontend/mobile: wire lead detail timeline, conversation, and metrics.
- [ ] Decide later if a separate static welcome template should be sent before/inside the AI reply flow.

## 15. CRM CONTACT / LEAD FRONTEND WIRING

- [x] Backend: separate saved Contacts from pipeline Leads.
- [x] Backend: manual contact CRUD via `/api/v1/contacts/`.
- [x] Backend: CSV contact upload via `/api/v1/contacts/upload-csv/` with duplicate rows.
- [x] Backend: paginated lead list via `/api/v1/leads/?page=1&page_size=20` with `hot_count`, `warm_count`, and `cold_count`.
- [x] Backend: paginated lead conversation history via `/api/v1/leads/{id}/conversation/`.
- [x] Backend: inbox list via `/api/v1/leads/inbox/` with latest message per lead.
- [x] Backend: auto-capture Sent.dm inbound texters as Contact + Lead.
- [x] Backend: link Contact and Lead records for cross-navigation.
- [ ] Frontend/mobile: wire separate Contacts tab to `/api/v1/contacts/`.
- [ ] Frontend/mobile: wire CSV upload duplicate review to `/api/v1/contacts/upload-csv/`.
- [ ] Frontend/mobile: wire Leads tab to paginated `/api/v1/leads/`.
- [ ] Frontend/mobile: wire hot/warm/cold counts from `/api/v1/leads/stats/`.
- [ ] Frontend/mobile: wire lead detail activity/metrics.
- [ ] Frontend/mobile: wire full paginated lead conversation from `/api/v1/leads/{id}/conversation/`.
- [ ] Frontend/mobile: wire inbox list from `/api/v1/leads/inbox/`.

## 16. USER CHESERA NUMBER DISPLAY

- [x] Backend: add `GET /api/v1/me/chesera-number/`.
- [x] Backend: return pending/unassigned state for free or not-yet-activated users.
- [x] Backend: return assigned Sent.dm SMS/RCS number when available.
- [x] Backend: document endpoint in Swagger.
- [ ] Frontend/mobile: show assigned Chesera number in the user's dashboard/profile.
- [ ] Frontend/mobile: show pending activation message when no number is assigned.

## 17. WELCOME MESSAGE AND STATELESS AI HELPER

- [x] Backend: add business setting `auto_welcome_message_enabled`.
- [x] Backend: add welcome message set/read endpoint.
- [x] Backend: queue welcome message task when contacts are manually created.
- [x] Backend: queue welcome message task when contacts are CSV imported.
- [x] Backend: keep Contacts as Contacts; welcome messages do not create Leads.
- [x] Backend: add stateless `tone` + `msg` AI message structuring endpoint.
- [ ] Frontend/mobile: add welcome message editor.
- [ ] Frontend/mobile: add profile setting toggle for automatic welcome messages.
- [ ] Frontend/mobile: call stateless AI structuring endpoint where users compose/edit messages.

## 18. WELCOME MESSAGE COMPLIANCE DECISION

- [x] Keep welcome-message implementation code present for reference.
- [x] Hide/comment out welcome-message template URL from frontend access.
- [x] Disable automatic welcome-message queueing from contact creation/import.
- [x] Disable Sent.dm welcome-message Celery task/send flow.
- [x] Keep stateless AI message structuring endpoint active.
- [ ] Future product decision: only re-enable welcome/first-touch messages with controlled provider-approved templates and explicit consent rules.
## 19. NOTIFICATIONS

- [x] Add app-level notification model/service/templates for Chesera.
- [x] Add REST notification API at `/api/v1/notifications/`.
- [x] Add read state actions: mark one read, mark all read, unread count, clear read.
- [x] Enforce normal users as REST-only notification recipients.
- [x] Add admin-only websocket notification consumer at `/ws/admin/notifications/?token=<jwt>`.
- [x] Configure Channels/Redis and ASGI/Daphne runtime support.
- [x] Add Nginx `/ws/` websocket proxy block with Upgrade headers.
- [x] Wire notification hooks into signup, subscription records, Sent.dm profile/campaign/WhatsApp actions, and inbound new-lead capture.
- [x] Add cleanup Celery task for old read notifications.
- [ ] Frontend/mobile: wire notification list, unread count, and read actions.
- [ ] Admin dashboard: wire websocket connection and live notification UI.
- [ ] Production: after deploy, confirm Daphne websocket handshake through Nginx for `/ws/admin/notifications/`.
