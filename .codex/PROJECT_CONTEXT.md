# CHESERA PROJECT CONTEXT

## CURRENT PRODUCT DIRECTION

Chesera is moving away from the active Twilio-first workflow for new messaging development.

The approved V1 messaging direction is:

- Sent.dm handles SMS.
- Sent.dm handles RCS.
- Sent.dm handles WhatsApp.
- Sent.dm handles dedicated messaging numbers.
- WhatsApp is optional in V1: agents may connect their own existing Meta-approved WABA using WABA ID, phone number ID, and access token.
- SMS/RCS activation must not be blocked by missing WhatsApp credentials.
- Inherited organization WhatsApp may support Sent.dm profile creation, but it is not treated as the agent-owned active WhatsApp channel.
- Each paid agent/company gets one isolated Sent.dm Sender Profile.
- Free users get dashboard access only, with no live messaging number.
- Agents never touch Sent.dm directly.
- Chesera owns the Sent.dm organization account and runs provisioning in the background.

Twilio code should remain untouched for now. Sent.dm should be added in parallel behind separate endpoints and models until the new flow is tested.

## CURRENT DJANGO STRUCTURE

This is a Django + Django REST Framework backend.

Important existing apps:

- `accounts`: custom phone-number users, full signup OTP start, OTP login/verification, current user, free trial claim.
- `business`: organizations, business settings, provider accounts, phone numbers, notification settings, current Twilio onboarding endpoints.
- `core`: reference data, free trial numbers, Twilio configuration/webhook endpoints.
- `communications`: conversations, messages, AI analysis, outbound queue, webhook-event concepts.
- `crm`: leads, lead activity, tags, reminders.
- `ai`: AI configuration, prompt templates, AI usage/model logs.
- `subscription`: plans, subscriptions, payments, purchase verification.
- `twilio_app`: Twilio TrustHub/A2P/Toll-Free-specific models and services.

## IMPORTANT CONSTRAINTS

- Do not remove or rewrite Twilio during the first Sent.dm implementation.
- Add Sent.dm as a separate integration path first.
- Do not hardcode API keys or webhook secrets.
- Store real provider credentials only in `.env`.
- Keep `.codex` files free of secrets.
- Every meaningful code change should also update the relevant `.codex` context/progress file.
- Track unfinished implementation work in `.codex/REMAINING_WORK.md`; update checklist statuses whenever work starts, completes, is blocked, or changes scope.

## CURRENT SENT.DM TEST STATUS

The client supplied a Sent.dm API key and account/user identifier. The API key was tested manually by the user:

- `GET /v3/me` works.
- `GET /v3/profiles` works and returned an empty profile list.
- `POST /v3/profiles` with `sandbox: true` returned a simulated Sender Profile response.

Important interpretation:

- The API key is valid for sandbox/API-shape testing.
- Sandbox responses do not prove real profile creation, real number provisioning, or real 10DLC submission.
- Sent.dm docs say real Sender Profile provisioning requires an organization account and an organization API key whose user has admin role.
- MCP verification on 2026-09-10 confirmed the connected Sent account returns `type: "organization"`, name `Chesera LLC`, and id `80c15901-8bd6-407f-b623-0958c0374a98`. Before live rollout, still confirm the deployed production environment uses the same intended organization key.

## CURRENT AUTH FLOW

- Signup starts with `POST /api/v1/client/auth/signup/` using full name, email, phone number, city, country, and optional country code.
- Signup creates or updates an unverified client user and sends a registration OTP. It rejects already verified phone numbers so users do not accidentally re-register.
- Login still uses `POST /api/v1/client/auth/send-otp/` and `POST /api/v1/client/auth/verify-otp/` for existing OTP auth compatibility.
- OTP verification returns JWT access/refresh tokens and the user profile including email, city, country, and country code.
- `PATCH /api/v1/me/` allows editable profile fields such as email, full name, city, country, country code, and profile picture, but keeps phone number, user type, phone verification status, and last activity read-only.
## CURRENT VERIFICATION BASELINE

Last known local checks:

- `python manage.py check` passed.
- Full Python compile passed after the local verification comma fix.
- Focused backend tests now cover subscription, Sent.dm profile/campaign helpers, optional WhatsApp payloads, webhook signature verification, STOP/HELP webhook processing, Sent.dm AI replies, and AI compliance prompt rules.


## CURRENT SENT.DM WEBHOOK PROCESSING STATE

As of 2026-09-09, the deployed HTTPS webhook URL receives Sent.dm events:

```text
https://api.trychesera.com/api/v1/sentdm/webhooks/inbound/
```

The backend now verifies Sent.dm webhook signatures, stores raw webhook events, parses inbound message payloads, maps them to Sender Profile, organization, lead, and conversation when possible, and stores inbound messages in both `SentDMMessage` and `communications.Message`.

STOP/STOPALL/UNSUBSCRIBE/CANCEL/END/QUIT are handled before any future AI processing. The matched lead is permanently opted out, AI is disabled, active conversations are closed, and pending follow-up reminders are suppressed. HELP sends the organization's configured help response through Sent.dm.

Celery/Redis async processing is now wired for inbound Sent.dm webhooks. The request path verifies/stores the webhook and queues `process_sentdm_webhook_event_task`; STOP/HELP processing and AI reply generation happen in the worker. Normal inbound messages are mirrored into the CRM conversation, passed to the existing AI service, sent back through the matched Sent.dm Sender Profile, and stored as outbound `SentDMMessage` plus `communications.Message`. HOT AI stages disable lead/conversation AI for handoff. The AI prompt now includes business identity, support email, approved vertical/use case, STOP opt-out guidance, and Sent.dm/10DLC-safe response rules. Outbound Sent.dm sends now share a channel policy: auto/SMS/RCS are allowed without WhatsApp, explicit WhatsApp requires an active WhatsApp number on the Sender Profile, and follow-up sends requested over WhatsApp route to SMS outside Meta's 24-hour customer-service window. The current follow-up task still sends push reminders only; actual Day 1/3/7/14 outbound lead messages remain a product-scope build item. See `.codex/REMAINING_WORK.md` for the live checklist. Production migration note: `FollowUpReminder.id` intentionally remains UUID to match existing deployed database history.

## SENT.DM VERIFICATION NOTES

Verified against Sent.dm docs and MCP on 2026-09-10:

- `POST /v3/messages` supports free-form `text`, but free-form text is intended for open/reply conversations. First outbound outreach to a contact should use an approved template.
- Sent's REST `channel` field is an array for explicit channels, e.g. `["sms"]`; auto routing is represented by omitting `channel` or using Sent's auto value. Our client keeps the internal API value `auto` and omits `channel` when sending to Sent.
- Explicit channel pinning disables automatic fallback. Cross-channel fallback is available only when using automatic selection.
- Sender Profile creation requires an organization account and admin-capable organization API key.
- Current Sent docs state each Sender Profile must either inherit an organization-level WhatsApp Business Account or include direct WABA credentials. If the organization WhatsApp channel is not configured and direct WABA fields are omitted, Sent may reject profile creation with HTTP 422.
- Chesera now tracks WhatsApp connection source/status separately. Inherited organization WhatsApp is recorded as not connected for the agent; direct agent WABA is required before WhatsApp is considered active for that Sender Profile.
- Outbound auto sends for a profile without active agent WhatsApp resolve to SMS locally so Sent.dm does not accidentally route through Chesera/org WhatsApp. Explicit WhatsApp sends fail for manual/direct messages unless direct agent WhatsApp is active; reply/follow-up flows can fall back to SMS.
- `/api/v1/me/plan-and-progress/` now returns backend activation state for subscription, business compliance, Sender Profile, number assignment, 10DLC campaign, SMS/RCS readiness, and optional WhatsApp state. Number assignment exposes `number_assignment_status` as `pending`, `assigned`, or `needs_attention`; pending numbers show the local-inventory delay message.
- MCP confirmed the connected account is an organization and has approved OPT_IN, OPT_OUT, and HELP templates, but MCP did not expose Sender Profile creation, webhook management, 10DLC submission, or channel configuration status tools.

## CURRENT CRM CONTACT / LEAD STATE

Superseded note from earlier on 2026-09-15: CRM contacts were briefly represented by `crm.Lead`; this was corrected later the same day. The current model uses separate `crm.Contact` and `crm.Lead` records.

Implemented backend behavior:

- Authenticated users can manage contacts/leads through `/api/v1/leads/`.
- Manual contact create supports full name, phone number with country code already embedded in `contact_number`, email, business name, notes, and lead stage.
- `business_name` is exposed in the API and stored internally in the existing `Lead.company` field.
- Contacts can be created before Sent.dm number assignment because `Lead.business_phone` is now optional.
- Lead source is tracked as `manual`, `csv_upload`, `auto_capture`, or `sentdm`.
- Hot/warm/cold are now first-class lead stages while older stages remain valid for compatibility.
- `/api/v1/leads/?stage=hot|warm|cold` filters lead lists by dashboard-friendly stage groups.
- `/api/v1/leads/stats/` returns total, hot, warm, cold, and opted-out counts.
- `/api/v1/leads/{id}/` returns lead details, activity timeline, conversation messages, score percentage, days in pipeline, total messages, inbound/outbound counts, source, and response rate.
- `/api/v1/leads/upload-csv/` imports contacts from CSV and returns created rows, duplicate rows, and row-level errors.
- Sent.dm inbound auto-capture now creates/updates the lead with source `auto_capture`, records `Lead created`, records `First reply received`, records `AI welcome sent` / `AI reply sent`, and records AI-driven stage changes.

Current caveats:

- CSV import accepts practical column aliases but does not yet support a rich frontend preview/confirm step.
- Auto-capture welcome behavior currently uses the existing Sent.dm AI reply path, not a separate static welcome-template engine.
- Follow-up outbound Day 1/3/7/14 messaging remains separate product scope.

## CURRENT CRM CONTACT VS LEAD MODEL

Updated on 2026-09-15 after product clarification:

- Contacts and leads are separate concepts in Chesera.
- `crm.Contact` is the user's saved address book: full name, country code, phone number, normalized contact number, email, business name, notes, and source.
- `crm.Lead` is the pipeline/conversation record created when a person engages through messaging or otherwise enters the lead flow.
- Manual contact save and CSV upload create Contacts only; they do not create Leads by themselves.
- `/api/v1/contacts/` is the address-book API.
- `/api/v1/contacts/upload-csv/` imports Contacts and returns duplicate rows separately.
- `/api/v1/leads/` is the paginated pipeline API with `page` and `page_size` query parameters.
- `/api/v1/leads/stats/` returns lead counts for total/hot/warm/cold/opted-out.
- Sent.dm inbound auto-capture creates or reuses a Contact, creates or reuses a Lead, and links them together.
- Lead detail includes activity timeline, conversation messages, score percentage, days in pipeline, source, response rate, and message counts.

## CURRENT USER CHESERA NUMBER ENDPOINT

As of 2026-09-15, the mobile/frontend app can fetch the authenticated user's dedicated Chesera SMS/RCS number from:

```text
GET /api/v1/me/chesera-number/
```

The endpoint does not require an active paid subscription because free/pending users still need a clear UI state. It returns `assigned=false` until a Sent.dm Sender Profile has a `phone_number`. The response includes the number assignment status, provider, profile id/status, and SMS/RCS active boolean.

## CURRENT WELCOME MESSAGE AND STATELESS AI MESSAGE ENDPOINTS

As of 2026-09-15:

- Users can configure a welcome message through `PUT/PATCH /api/v1/message-templates/welcome/`.
- Welcome text is stored in the existing `communications.StaticMessageTemplate` table using `template_type=WELCOME`.
- Business settings now include `auto_welcome_message_enabled`.
- When `auto_welcome_message_enabled=true`, manually created contacts and CSV-imported contacts queue a Celery task to send the configured welcome message.
- Welcome sending does not create a Lead. The contact becomes a Lead only when they reply/message into Chesera and the inbound Sent.dm webhook auto-captures them.
- Welcome send status is recorded under `Contact.metadata["welcome_message"]` when the task runs.
- The stateless AI helper endpoint is `POST /api/v1/ai/messages/structure/`; it accepts `tone` and `msg`, returns `structured_msg`, and does not read or write database records beyond authentication.

## WELCOME MESSAGE FLOW DISABLED

Updated on 2026-09-15 after compliance review:

- Automatic welcome-message sending is intentionally disabled.
- `communications/urls.py` keeps the welcome template URL commented out, so frontend/mobile cannot configure dynamic welcome messages.
- `crm.views.enqueue_contact_welcome_message()` is a no-op and preserves the previous queueing code only as commented reference.
- `sentdm.tasks.send_contact_welcome_message_task` is commented out.
- `sentdm.services.send_welcome_message_to_contact()` has an early disabled return and preserves the previous implementation only as unreachable reference.
- This avoids dynamic first-touch message risk across SMS/10DLC and WhatsApp.
- `POST /api/v1/ai/messages/structure/` remains active and should still be used for stateless message drafting.

## CURRENT CRM LEAD LIST, INBOX, AND CONVERSATION API

Updated on 2026-09-15:

- `GET /api/v1/leads/` remains the paginated pipeline lead list and now includes `hot_count`, `warm_count`, and `cold_count` in the paginated response envelope.
- The count values respect source/search filters but are not narrowed by the current `stage` filter, so the frontend can show all three stage counters while the list is filtered.
- `GET /api/v1/leads/{id}/` remains a detail endpoint with compact lead detail, activity timeline, metrics, and the existing conversation field for backward compatibility.
- `GET /api/v1/leads/{id}/conversation/` is the frontend conversation-screen endpoint. It returns the full message history for that lead using normal pagination.
- `GET /api/v1/leads/inbox/` returns one row per lead that has messages, including lead fields, metrics, unread message count, and the latest message. It does not duplicate leads per message.
## CURRENT NOTIFICATION SYSTEM

Updated on 2026-09-15:

- `notifications` is now the active app-level notification system for Chesera.
- REST notifications are available to all authenticated users at `/api/v1/notifications/`.
- Normal/client users only receive REST/API-based notifications.
- Admin/staff users receive the same REST notification records plus websocket pushes at `/ws/admin/notifications/?token=<jwt>`.
- Websocket access is admin-only; non-admin tokens are rejected by the consumer.
- Notification templates currently cover: welcome/signup, new user admin alert, subscription record/active, Sent.dm Sender Profile request/completion, 10DLC campaign request, WhatsApp connection request, new lead captured, and system alerts.
- Notification hooks are wired into signup, IAP subscription creation, Sent.dm profile/campaign/WhatsApp actions, and Sent.dm inbound new-lead auto-capture.
- Production now runs through Daphne/ASGI so HTTP and websocket traffic can share the same backend service. Channels uses Redis through `CHANNEL_REDIS_URL`, defaulting to `CELERY_BROKER_URL`. Nginx config includes a `/ws/` proxy block with Upgrade headers for admin notification websockets.
