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

## 2026-08-30 - SWAGGER TWILIO CLEANUP

Completed:

- Commented Twilio-era URL registrations so they no longer appear in Swagger.
- Hidden business Twilio subaccount setup/sync endpoints.
- Hidden business phone-number router endpoints.
- Hidden core free-trial number inventory endpoints.
- Hidden core Twilio inbound webhook endpoint.
- Hidden account free-trial number claim endpoint.
- Disabled the subscription `claim-free-trail` router action by commenting its `@action` decorator.
- Removed Twilio/free-trial/phone-number Swagger tag metadata and schema mappings.
- Left Twilio implementation files, app registration, models, migrations, and config untouched for stability.

Validation run:

- `python manage.py check` passed.
- `python manage.py test sentdm` passed with 9 tests.
- `python -m compileall -q accounts business core sentdm cheshara_config` passed.
- `python -m compileall -q subscription` passed.
- `python manage.py spectacular --file tmp_schema.yml --validate` completed successfully with only older unrelated schema warnings/errors from existing non-Twilio APIViews.
- Generated schema search confirmed no Twilio/free-trial-number/phone-number/sub-account paths or old Twilio docs tags remain visible.

Current Swagger direction:

- Sent.dm endpoints remain visible under the `Sent.dm` tag.
- Twilio-era messaging/number endpoints are kept in code comments but removed from active API docs.

## 2026-08-30 - VIEW-LEVEL SWAGGER DOCUMENTATION

Completed:

- Added view-level drf-spectacular documentation for active API endpoints using `extend_schema` and `extend_schema_view`.
- Documented active auth endpoints under `Auth - User`, `Auth - Admin`, and `Auth - Token`.
- Documented current user and plan/progress endpoints.
- Documented active business profile, business settings, onboarding status, and notification endpoints.
- Documented active reference-data endpoints for business types and industries.
- Documented subscription plan, user subscription, purchase, and purchase verification endpoints.
- Expanded Sent.dm endpoint docs with clear sandbox/live behavior, Sender Profile onboarding, and webhook descriptions.
- Kept disabled Twilio-era routes out of active docs.
- Added serializer field schema hints for computed business/subscription fields.
- Added a schema-safe queryset guard for user subscriptions.
- Added a drf-spectacular enum override for the shared subscription billing cycle enum.

Validation run:

- `python manage.py check` passed.
- `python manage.py test sentdm` passed with 9 tests.
- `python -m compileall -q accounts business core subscription sentdm cheshara_config` passed.
- `python manage.py spectacular --file tmp_schema.yml --validate` passed with 0 warnings and 0 errors.

Current Swagger state:

- Documentation now comes from view-level annotations for the active API surface.
- `core/schema.py` remains as a fallback grouping layer for future endpoints that may not yet have explicit tags.

## 2026-08-30 - SENT.DM PROFILE ID FLOW CLARIFICATION

Completed:

- Confirmed `/api/v1/sentdm/profiles/complete/` expects the Sent.dm `profile_id` UUID returned by `/api/v1/sentdm/profiles/create/`, not a local database row ID like `1`.
- Updated the not-found response to explicitly tell testers to use `data.profile.profile_id` from the create response.
- Fixed profile creation so the Swagger payload fields `name`, `short_name`, `description`, and `email` are included in the Sent.dm create-profile payload instead of being ignored.
- Added a regression test for request payload override behavior.

Validation run:

- `.venv\Scripts\python.exe -m compileall -q sentdm` passed.
- `.venv\Scripts\python.exe manage.py test sentdm` passed with 10 tests.
- `.venv\Scripts\python.exe manage.py check` passed.

## 2026-08-30 - SENT.DM PAID ACCESS AND COMPLIANCE FIELDS

Completed:

- Added Sent.dm/10DLC compliance fields to `business.Organization` for legal name, tax ID, vertical, authorized representative, support contact, policy URLs, opt-in details, sample messages, autoresponses, and expected volume.
- Exposed the new fields through business profile setup/update serializers and Django admin under `Sent.dm Compliance`.
- Added `business/migrations/0030_organization_sentdm_compliance_fields.py`.
- Added `sentdm.permissions.HasActivePaidSubscription` using the existing `SubscriptionValidationService.get_paid_active_subscription(user)` source of truth.
- Applied the paid-subscription gate to all authenticated Sent.dm control endpoints while leaving inbound/profile-ready webhooks public for Sent.dm delivery.
- Kept profile creation manual/frontend-triggered for now; no subscription webhook or automatic activation trigger added yet.
- Kept OTP migration out of scope for now.

Validation run:

- `.venv\Scripts\python.exe -m compileall -q business sentdm` passed.
- `.venv\Scripts\python.exe manage.py check` passed.
- `.venv\Scripts\python.exe manage.py test sentdm` passed with 11 tests.
- `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` reported no changes detected.
- `.venv\Scripts\python.exe manage.py spectacular --file tmp_schema.yml --validate` passed; generated `tmp_schema.yml` was removed afterward.

## 2026-08-30 - SENT.DM 10DLC READINESS AND CAMPAIGN LAYER

Completed:

- Added `sentdm_messaging_use_case_us` and corrected the volume field to `sentdm_expected_daily_volume` before the new business migration is applied.
- Added local `SentDMCampaign` tracking model, admin registration, and migration `sentdm/migrations/0002_sentdmcampaign.py`.
- Added Sent.dm campaign readiness service logic that reports missing compliance fields, sample-message count, selected use case, and profile availability.
- Added Sent.dm 10DLC campaign payload builder using the documented `/v3/profiles/{profileId}/campaigns` shape.
- Added manual API endpoints:
  - `GET /api/v1/sentdm/compliance/readiness/`
  - `POST /api/v1/sentdm/campaigns/create/`
- Added `SentDMClient.update_profile()` so campaign creation can turn off inherited campaign mode before creating a dedicated per-profile campaign.
- Kept profile/campaign creation manual for sandbox/frontend testing; no subscription-upgrade automation, OTP migration, or webhook-driven activation UI added yet.

Validation run:

- `.venv\Scripts\python.exe -m compileall -q business sentdm` passed.
- `.venv\Scripts\python.exe manage.py check` passed.
- `.venv\Scripts\python.exe manage.py test sentdm` passed with 12 tests.
- `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` reported no changes detected.
- `.venv\Scripts\python.exe manage.py spectacular --file tmp_schema.yml --validate` passed; generated `tmp_schema.yml` was removed afterward.
