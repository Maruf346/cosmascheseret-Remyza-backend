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

Updated on 2026-10-06:

- The same endpoint now includes `qr_payload` and `qr_code_base64`.
- When a Chesera number is assigned, `qr_payload` uses `sms:+number` so scanning the QR opens a message flow to the assigned Chesera number.
- QR images are generated on request using `qrcode[pil]`; they are not stored in the database.
- Assigned-number responses include `Cache-Control: private, max-age=3600` so clients can cache the QR briefly while still reflecting future number changes.

## CURRENT USER PROFILE TIMEZONE

Updated on 2026-10-06:

- User profiles now include optional `timezone`.
- Signup does not require timezone.
- `PATCH /api/v1/me/` can update timezone after signup.
- Timezone values are validated as IANA names, for example `America/New_York`, `America/Chicago`, `Asia/Dhaka`, or `UTC`.

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

## CURRENT AUTOMATED FOLLOW-UP SEQUENCE

Updated on 2026-10-07:

- Manual `FollowUpReminder` records remain in place for future/internal reminder use.
- Customer-facing follow-up messages use the separate `crm.AutomatedFollowUp` model.
- New auto-captured inbound leads get backend-controlled follow-ups scheduled for Day 1, Day 3, Day 7, and Day 14.
- Follow-up message text is fixed in the backend and includes STOP opt-out language; agents cannot write custom follow-up text.
- Due follow-ups are sent by `sentdm.tasks.send_due_automated_follow_ups_task`, scheduled every minute through `CELERY_BEAT_SCHEDULE`.
- Follow-ups use the existing Sent.dm outbound channel policy with `purpose="follow_up"`.
- Follow-ups outside WhatsApp's 24-hour customer-service window route to SMS when the requested channel is WhatsApp/auto.
- Follow-up scheduled, sent, and failed states create normal REST notifications for the agent/user.
- STOP/opt-out cancels pending automated follow-ups and marks existing manual reminders as sent/stopped.

## CURRENT SENT.DM WHATSAPP CONFIG API

Updated on 2026-10-08:

- `POST /api/v1/sentdm/profiles/whatsapp/connect/` connects or updates the agent-owned WhatsApp Business configuration.
- `GET /api/v1/sentdm/profiles/whatsapp/connect/` returns the authenticated paid user's saved WhatsApp configuration:
  - `profile_id`
  - `waba_id`
  - `phone_number_id`
  - `access_token`
- WhatsApp config is stored on the user's `Organization`; `profile_id` comes from the current local `SentDMProfile` when available.
- The GET endpoint is for paid/authenticated users and returns blank strings for missing saved values.

## CURRENT SENT.DM 10DLC OPT-IN COMPLIANCE FLOW

Updated on 2026-10-10:

- Sent.dm MCP confirmed that US 10DLC Sender Profile setup should be sent through `sender_profiles.create` with `smsCountry=US`, `smsNumberType=TEN_DLC`, and nested `compliance.brand` plus `compliance.campaign`.
- Chesera now stores structured brand registration fields on `Organization`:
  - `sentdm_tax_id_type`
  - `sentdm_ein_issuing_country`
  - `sentdm_entity_type`
  - `sentdm_brand_street`
  - `sentdm_brand_city`
  - `sentdm_brand_state`
  - `sentdm_brand_postal_code`
- Chesera now stores structured SMS opt-in evidence fields on `Organization`:
  - `sentdm_opt_in_method`
  - `sentdm_opt_in_starting_url`
  - `sentdm_opt_in_form_url`
  - `sentdm_opt_in_screenshot_url`
  - `sentdm_opt_in_checkbox_text`
  - `sentdm_sms_disclaimer_text`
  - `sentdm_privacy_policy_no_mobile_sharing`
  - `sentdm_sms_consent_optional`
  - `sentdm_sms_checkbox_not_prefilled`
  - `sentdm_marketing_messages_disclosed`
  - `sentdm_donation_solicitation_disclosed`
- Supported opt-in methods are `web`, `spoken`, `physical`, and `subscriber_initiated`.
- Backend readiness checks now block Sender Profile/campaign setup when required brand fields or method-specific opt-in evidence is missing.
- Backend generates Sent.dm `compliance.campaign.message_flow` from structured fields, so frontend/client users do not need to manually write a reviewer-perfect 10DLC message flow.
- Sender Profile creation payload now includes `smsCountry`, `smsNumberType`, and `compliance` directly in the profile create request.

## CURRENT ADMIN USER MANAGEMENT API

Updated on 2026-10-10:

- Admin/staff users can manage users through `/api/v1/admin/users/`.
- `GET /api/v1/admin/users/` is paginated and returns:
  - summary counts: `total_users`, `total_active`, `total_blocked`, `total_on_trial`
  - rows with `user_id`, `user_name`, `business_name`, `profile_pic`, `email`, `phone`, `plan`, `messages_sent_count`, `leads_count`, `is_active`, and `joined_date`
- Supported list filters:
  - `plan=pro|trial|free`
  - `is_active=true|false`
  - `search=` across user name, phone, email, and business name
- `GET /api/v1/admin/users/{user_id}/` returns detailed user, organization, subscription, lead/message count, and status data.
- `PATCH /api/v1/admin/users/{user_id}/` accepts `{ "is_active": true|false }`.
- The API maps `is_active` to the existing `User.status` field:
  - `true` -> `ACTIVE`
  - `false` -> `INACTIVE`
- `DELETE /api/v1/admin/users/{user_id}/` deletes a user account.
- `GET /api/v1/admin/users/export/` exports the filtered user list as CSV.
- `supports/migrations/0001_initial.py` exists because `supports.Feedback.user` participates in user delete cascades.
- Admin user retrieve also includes `days_active`, `response_rate`, `business_type`, `timezone`, humanized `last_active`, `chesera_number`, and expanded `subscription` plan details including price, start date, and next renewal.
- Admin user export supports:
  - `format=csv|xlsx`
  - `delimiter=comma|semicolon|tab`
  - `date_range=all_time|last_week|last_month`
  - `columns=` with selected fields
- Exportable columns are `user_id`, `full_name`, `email`, `phone`, `business_name`, `business_type`, `plan`, `status`, `messages_sent_count`, `leads_count`, `joined_date`, `last_active`, and `chesera_number`.
- XLSX export requires `openpyxl`, which is pinned in `requirements.txt`.

## CURRENT SWAGGER / OPENAPI DOCUMENTATION STANDARD

Updated on 2026-10-08:

- Swagger should document the actual API response envelope, not only the inner model serializer.
- Response serializers have been added for key auth, account, AI, welcome-message, Sent.dm profile, and WhatsApp config endpoints.
- `SPECTACULAR_SETTINGS["GENERIC_ADDITIONAL_PROPERTIES"] = None` is enabled so generic JSON/object fields no longer show noisy `additionalProp1` placeholder fields in Swagger.
- `GET /api/v1/me/` documents the full current-user response envelope, including the nested user object, active subscription flags/details, and free-trial details.
- Paginated list endpoints should document the real pagination envelope with `count`, `next`, `previous`, and `results`.
- CRM contacts, CRM leads, lead inbox, lead conversation messages, notifications, and user subscriptions all use explicit paginated Swagger response serializers.
- `GET /api/v1/user-subscription/` is paginated at runtime and supports `page` plus `page_size`.
- Small reference-data lists such as business types and industries are not paginated, but Swagger documents their actual `{ success, count, data }` envelope.
- Hidden/legacy Twilio endpoints remain outside the current cleanup scope unless they are re-enabled.
- `GET /api/v1/me/plan-and-progress/` documents its full nested response body, including subscription status, organization, Sent.dm compliance readiness, Sender Profile, 10DLC campaign, number assignment, WhatsApp status, messaging activation, and onboarding progress steps.
- `GET /api/v1/me/onboarding-status/` documents the real `{ success, data: { onboarding_step } }` response body.
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
## CURRENT WELCOME MESSAGE PRESET API

Updated on 2026-10-06:

- Free-form welcome message editing remains disabled for compliance safety.
- The legacy `/api/v1/message-templates/welcome/` route remains commented out and inaccessible.
- Backend-owned preset welcome messages are exposed at `/api/v1/welcome-message/`.
- Supported preset keys are `professional`, `friendly`, and `casual`.
- `GET /api/v1/welcome-message/` returns all presets plus the user's selected preset when configured.
- `GET /api/v1/welcome-message/?template=professional` returns one preset and the current selection.
- `PUT/PATCH /api/v1/welcome-message/` accepts only `{ "template": "professional|friendly|casual" }` and stores the selected backend-owned template in `StaticMessageTemplate`.
- Custom message text is not accepted through this API; frontend should only let users choose one of the backend presets.
