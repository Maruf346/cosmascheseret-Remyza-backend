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

## 2026-08-30 - SUBSCRIPTION FLOW REPLACED WITH IAP RECORDS

Completed:

- Replaced the active subscription API flow with Apple/Google in-app subscription payment records using the existing `UserSubscription` model.
- Kept the migration non-destructive: legacy plan/payment/invoice/purchase-info tables remain in code/database compatibility, but old plan/purchase endpoints are no longer routed or documented.
- Added IAP fields to `UserSubscription`: product ID, plan type, medium, purchase token, transaction/original transaction/order IDs, store environment/status, active flag, purchase/expiry dates, amount/currency, verification payload, and app bundle ID.
- Made `UserSubscription.plan` optional so mobile IAP records do not require backend-managed subscription plans.
- Replaced active API routes with only:
  - `GET /api/v1/user-subscription/`
  - `POST /api/v1/user-subscription/`
  - `GET /api/v1/user-subscription/{id}/`
- Admin users can list/retrieve all records through the API; client users can list/retrieve only their own records.
- Django admin now focuses on `UserSubscription` and allows staff to manually change `is_subscription_active`, `store_status`, and `expiry_date` for testing/support.
- Updated `SubscriptionValidationService` so Sent.dm paid-access checks use active, unexpired IAP subscription records.
- Updated current-user and plan-progress responses to read `plan_type` and `expiry_date` from IAP subscription records.
- Made legacy free-trial expiration task a no-op because free users are dashboard-only in the Sent.dm/IAP flow.
- Removed old subscription plan/purchase Swagger tags and fallback schema mappings.

Validation run:

- `.venv\Scripts\python.exe -m compileall -q subscription accounts sentdm core` passed.
- `.venv\Scripts\python.exe manage.py test subscription sentdm` passed with 17 tests.
- `.venv\Scripts\python.exe manage.py check` passed.
- `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` reported no changes detected.
- `.venv\Scripts\python.exe manage.py spectacular --file tmp_schema.yml --validate` passed.
- Generated schema search confirmed only `/api/v1/user-subscription/` and `/api/v1/user-subscription/{id}/` remain for subscriptions; old `subscription-plans`, `purchase-verify`, and `current-plan` routes are gone.

## 2026-08-30 - FIXED SUBSCRIPTION AND BUSINESS MIGRATION RUNTIME ERRORS

Issue:

- `GET /api/v1/user-subscription/` failed with `OperationalError: no such column: organizations.sentdm_messaging_use_case_us`.
- Root cause: `business.0030` was already applied before `sentdm_messaging_use_case_us` was added to the model/migration file, so Django marked the migration applied but the live database did not have that late-added column.

Completed:

- Added corrective migration `business/migrations/0031_ensure_sentdm_messaging_use_case_us_column.py`.
- The migration adds `organizations.sentdm_messaging_use_case_us` only when the column is missing, so existing DBs are fixed and fresh DBs safely no-op if `0030` already created the column.
- Applied migrations locally with `.venv\Scripts\python.exe manage.py migrate`.
- Added endpoint-level tests for the replacement `UserSubscriptionViewSet`:
  - client users list only their own subscription records
  - admin users list all subscription records
  - clients can create IAP subscription payment records

Validation run:

- `.venv\Scripts\python.exe manage.py test subscription sentdm` passed with 20 tests.
- `.venv\Scripts\python.exe manage.py check` passed.
- `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` reported no changes detected.
- `.venv\Scripts\python.exe manage.py spectacular --file tmp_schema.yml --validate` passed.
- Generated schema search confirmed only `/api/v1/user-subscription/` and `/api/v1/user-subscription/{id}/` remain for the subscription API.

## 2026-08-30 - SUBSCRIPTION ADMIN IAP ADD FLOW CLEANUP

Completed:

- Hid legacy backend-plan fields from the Django admin add/change form for `UserSubscription`.
- Admin now shows only the Apple/Google IAP fields needed for manual testing/support: user, organization, medium, product ID, plan type, store IDs, store status, active flag, purchase/expiry dates, amount/currency, and payload.
- Added `UserSubscriptionAdmin.save_model()` to auto-fill organization from the selected user, auto-fill purchase/start dates, mirror `expiry_date` into legacy `expires_at`, and sync legacy `status` based on `is_subscription_active`.
- Updated `UserSubscription.start_date` to default to `timezone.now` so admin-created subscriptions no longer require hidden legacy setup fields.
- Generated and applied `subscription/migrations/0017_alter_usersubscription_start_date.py` locally.

Validation run:

- `.venv\Scripts\python.exe manage.py migrate subscription` applied `0017` successfully.
- `.venv\Scripts\python.exe manage.py test subscription sentdm` passed with 20 tests.
- `.venv\Scripts\python.exe manage.py check` passed.
- `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` reported no changes detected.
## 2026-08-30 - Plan Progress Endpoint Sent.dm/IAP Fix

- Kept `/api/v1/me/plan-and-progress/` because the mobile app still needs one place to read subscription status plus setup progress.
- Reworked the endpoint away from the old Twilio/TFV flow. It now reports: subscription active, business profile created, compliance details added, Sent.dm Sender Profile created, and 10DLC campaign submitted.
- Added `business/migrations/0032_normalize_sentdm_expected_daily_volume.py` to repair malformed `sentdm_expected_daily_volume` values that were stored as text and caused `ValueError` in `OrganizationSerializer`.
- Applied the migration locally; the bad row was normalized to integer `0`.
- Added regression coverage for the endpoint in `accounts/tests.py`.
- Verification passed:
  - `.venv\Scripts\python.exe manage.py migrate business`
  - `.venv\Scripts\python.exe -m compileall -q accounts business`
  - `.venv\Scripts\python.exe manage.py check`
  - `.venv\Scripts\python.exe manage.py test accounts subscription sentdm`
  - `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`
  - `.venv\Scripts\python.exe manage.py spectacular --file tmp_schema.yml --validate`
## 2026-08-30 - Sent.dm Paid Onboarding Guard

- Added a Sent.dm profile-creation readiness check before calling the provider.
- `/api/v1/sentdm/profiles/create/` now stops early with clear `missing_fields` and per-field messages when the paid user has not completed the required business/10DLC compliance fields.
- The same endpoint now rejects duplicate Sender Profile creation with the existing `profile_id` and status, instead of silently creating another profile or calling Sent.dm again.
- Free users remain dashboard-only through `HasActivePaidSubscription`; paid users must also have a complete business compliance profile before Sender Profile creation.
- Added tests for missing compliance fields and duplicate profile handling.
- Verification passed:
  - `.venv\Scripts\python.exe -m compileall -q sentdm`
  - `.venv\Scripts\python.exe manage.py test sentdm`
  - `.venv\Scripts\python.exe manage.py test accounts subscription sentdm`
  - `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`
  - `.venv\Scripts\python.exe manage.py spectacular --file tmp_schema.yml --validate`

## 2026-09-01 - Optional Per-Agent WhatsApp WABA Fields

- Finalized WhatsApp as an optional V1 channel for agents who already have a Meta-approved WhatsApp Business Account/WABA.
- Added optional business onboarding fields: `sentdm_whatsapp_waba_id`, `sentdm_whatsapp_phone_number_id`, and `sentdm_whatsapp_access_token`.
- Generated and applied `business/migrations/0033_organization_sentdm_whatsapp_access_token_and_more.py`.
- Business serializers now require the WhatsApp fields as an all-or-none group: all blank skips WhatsApp, partial config is rejected, all three enables inclusion in the Sent.dm Sender Profile payload.
- `sentdm_whatsapp_access_token` is write-only and removed from normal organization API responses.
- `build_profile_payload()` now sends `whatsapp_business_account` to Sent.dm only when all three WhatsApp config values are present.
- Profile creation errors now include a WhatsApp-specific hint when Sent.dm rejects a request that included WhatsApp credentials.
- Live WhatsApp-only sends now require `SentDMProfile.whatsapp_phone_number`; otherwise the endpoint tells clients to connect/verify WhatsApp first or use auto/SMS/RCS.
- Updated `.codex/PROJECT_CONTEXT.md`, `.codex/SENTDM_WORKFLOW.md`, and `.codex/DECISIONS.md` with the finalized optional WhatsApp architecture.
- Verification passed:
  - `.venv\Scripts\python.exe manage.py migrate business`
  - `.venv\Scripts\python.exe manage.py test accounts business subscription sentdm`
  - `.venv\Scripts\python.exe -m compileall -q business sentdm`
  - `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`
  - `.venv\Scripts\python.exe manage.py check`
  - `.venv\Scripts\python.exe manage.py spectacular --file tmp_schema.yml --validate`
