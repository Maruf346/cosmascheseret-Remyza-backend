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
- Each paid agent/company gets one isolated Sent.dm Sender Profile.
- Free users get dashboard access only, with no live messaging number.
- Agents never touch Sent.dm directly.
- Chesera owns the Sent.dm organization account and runs provisioning in the background.

Twilio code should remain untouched for now. Sent.dm should be added in parallel behind separate endpoints and models until the new flow is tested.

## CURRENT DJANGO STRUCTURE

This is a Django + Django REST Framework backend.

Important existing apps:

- `accounts`: custom phone-number users, OTP login, current user, free trial claim.
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

## CURRENT SENT.DM TEST STATUS

The client supplied a Sent.dm API key and account/user identifier. The API key was tested manually by the user:

- `GET /v3/me` works.
- `GET /v3/profiles` works and returned an empty profile list.
- `POST /v3/profiles` with `sandbox: true` returned a simulated Sender Profile response.

Important interpretation:

- The API key is valid for sandbox/API-shape testing.
- Sandbox responses do not prove real profile creation, real number provisioning, or real 10DLC submission.
- Sent.dm docs say real Sender Profile provisioning requires an organization account and an organization API key whose user has admin role.
- Before live rollout, confirm `GET /v3/me` returns `type: "organization"` with the production organization key.

## CURRENT VERIFICATION BASELINE

Last known local checks:

- `python manage.py check` passed.
- Full Python compile passed after the local verification comma fix.
- Existing Django tests contain no real coverage and `manage.py test` reports 0 tests.

