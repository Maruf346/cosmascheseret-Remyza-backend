# SENT.DM IMPLEMENTATION PLAN

## IMPLEMENTATION STRATEGY

Build Sent.dm in parallel with Twilio.

Do not replace or delete Twilio code during the sandbox phase. The first goal is to prove Sent.dm independently.

## RECOMMENDED APP STRUCTURE

Create a dedicated Django app:

```text
sentdm/
  __init__.py
  apps.py
  choices.py
  client.py
  models.py
  serializers.py
  services.py
  tasks.py
  urls.py
  views.py
  tests.py
```

## ENVIRONMENT VARIABLES

Add placeholders only. Never commit real secrets.

```env
SENTDM_API_BASE=https://api.sent.dm/v3
SENTDM_API_KEY=
SENTDM_ORGANIZATION_ID=
SENTDM_SANDBOX_MODE=True
SENTDM_WEBHOOK_SECRET=
```

## INITIAL ENDPOINTS

Add under `/api/v1/sentdm/`:

```text
GET  /account/check/
GET  /profiles/
POST /profiles/create/
GET  /profiles/current/
POST /profiles/complete/
POST /messages/send-sandbox/
POST /webhooks/inbound/
POST /webhooks/profile-ready/
```

## INITIAL MODELS

Start with separate Sent.dm models so Twilio remains untouched.

Suggested models:

```text
SentDMProfile
- user
- organization
- profile_id
- status
- phone_number
- raw_response
- created_at
- updated_at

SentDMMessage
- organization
- lead
- conversation
- sent_message_id
- direction
- channel
- from_number
- to_number
- body
- status
- raw_response

SentDMWebhookEvent
- event_id
- event_type
- payload
- processed
- processed_at
- error
```

## SERVICE LAYER

`sentdm/client.py` should be a thin API wrapper:

```text
get_account()
list_profiles()
create_profile()
get_profile()
complete_profile()
create_campaign()
send_message()
create_webhook()
test_webhook()
```

`sentdm/services.py` should map Chesera models to Sent.dm workflows:

```text
provision_profile_for_organization()
start_profile_completion()
send_outbound_message()
normalize_inbound_webhook()
handle_opt_out_or_help()
```

## TASKS

Webhook processing should run in background tasks.

If Celery is not already configured, use a small synchronous fallback for local development but keep the code boundary task-ready.

Target async flow:

```text
webhook view
-> verify signature
-> store event
-> enqueue task
-> return 200
```

## TESTING PHASES

Phase 1: Sandbox API tests

- Account check.
- Profile list.
- Profile create with `sandbox: true`.
- Campaign create with `sandbox: true`.
- Profile complete with `sandbox: true`.
- Send message with `sandbox: true`.

Phase 2: Local webhook tests

- Run Django locally.
- Expose local API with HTTPS tunnel.
- Register/test Sent.dm webhook URL.
- Store webhook secret in `.env`.
- Verify signature.
- Log raw payload.
- Simulate inbound message processing.

Phase 3: Controlled live pilot

- Disable sandbox.
- Create one real test Sender Profile.
- Submit/complete compliance.
- Wait for real 10DLC/profile approval.
- Confirm number activation.
- Send and receive real messages.
- Confirm AI reply flow and opt-out behavior.

## OPEN QUESTIONS BEFORE LIVE

- Does `GET /v3/me` return `type: "organization"` with the production organization key?
- Does the API key user have admin role?
- Are SMS, WhatsApp, and RCS channels configured for live use?
- What is the exact webhook payload shape for inbound messages?
- What is the exact Sent.dm send-message response shape?
- How does the production profile response expose the assigned phone number?
- Which Sent.dm events should be subscribed for V1?
## CURRENT IMPLEMENTATION STATUS

Completed in the first Sent.dm sandbox slice:

- Added dedicated `sentdm` Django app in parallel with Twilio.
- Added Sent.dm settings and `.env.example` placeholders without committing real secrets.
- Exposed `/api/v1/sentdm/` endpoints for account checks, profile list/create/current/complete, sandbox message send, and webhook ingestion.
- Added Sent.dm Swagger grouping under the `Sent.dm` tag.
- Added models for Sender Profiles, Sent.dm messages, and raw webhook events.
- Added API client wrapper that adds `"sandbox": true` only when `SENTDM_SANDBOX_MODE=True`.
- Added webhook signature verification helper using HMAC-SHA256 over the raw request body.
- Added initial unit tests for sandbox payload switching, webhook signature verification, and profile status normalization.

Current required env values for local sandbox work:

```env
SENTDM_API_BASE=https://api.sent.dm/v3
SENTDM_API_KEY=
SENTDM_ORGANIZATION_ID=
SENTDM_SANDBOX_MODE=True
SENTDM_WEBHOOK_SECRET=
SENTDM_WEBHOOK_TOLERANCE_SECONDS=300
```

`SENTDM_ORGANIZATION_ID` is optional for now. It is intended only as a future safety check to confirm the API key belongs to the expected Chesera organization before live onboarding. API calls currently authenticate with `SENTDM_API_KEY`.

## LIVE SEND ACTIVATION RULE

The live Sent.dm send code path has been prepared but is intentionally not exposed in `sentdm/urls.py` yet.

Current active route:

```text
POST /api/v1/sentdm/messages/send-sandbox/
```

Prepared but commented route:

```text
POST /api/v1/sentdm/messages/send/
```

Activation checklist before uncommenting the live route:

- `SENTDM_SANDBOX_MODE=False` is set only in the production environment.
- `SENTDM_API_KEY` is a confirmed live organization/admin API key.
- `SENTDM_WEBHOOK_SECRET` is configured from the live Sent.dm webhook endpoint.
- Agent Sender Profiles are approved/live, not sandbox-only simulated profiles.
- Real lead/conversation routing is connected, including STOP/HELP handling and async webhook processing.
- Frontend/client usage of `send-sandbox` is retired or restricted to development only.

Guardrails now in code:

- `send-sandbox` rejects requests when `SENTDM_SANDBOX_MODE=False`.
- The live `send` view rejects requests when `SENTDM_SANDBOX_MODE=True`.
- The live `send` view requires a Sent.dm Sender Profile before sending.
