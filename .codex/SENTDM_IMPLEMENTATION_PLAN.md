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
SENTDM_ACCOUNT_ID=
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

