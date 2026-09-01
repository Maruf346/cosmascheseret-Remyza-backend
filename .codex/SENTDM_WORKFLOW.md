# SENT.DM WORKFLOW

## APPROVED ARCHITECTURE

Chesera uses one main Sent.dm organization account.

Each paid agent/company gets one isolated Sender Profile under that Sent.dm organization.

The agent never creates a Sent.dm account, never buys a number manually, never submits compliance manually, and never manages channel routing. Chesera handles the setup in the background.

## FREE USER FLOW

When a user signs up for a free account:

1. The user gets access to the Chesera dashboard.
2. They can set up their business profile.
3. They can configure AI and business settings.
4. They can prepare lead management, templates, and dashboard data.
5. They do not get a live SMS/RCS/WhatsApp messaging number.
6. No public messaging activation starts until they upgrade to paid.

## PAID USER FLOW

When a user upgrades to paid:

1. Chesera starts messaging provisioning in the background.
2. Chesera creates a Sent.dm Sender Profile for the agent/company.
3. Chesera submits or attaches required business/compliance data.
4. Chesera starts SMS/10DLC approval for US messaging.
5. A dedicated messaging number is provisioned or assigned.
6. Sent.dm completes/updates the profile status asynchronously.
7. Chesera updates the agent dashboard with activation status.
8. Once approved, the agent can receive and reply to leads through Chesera.

Customer-facing activation copy should stay honest:

> Your messaging setup is being activated. Most users are ready to send and receive messages within 1-3 business days after upgrading.

Do not promise instant activation.

## DEDICATED NUMBER FLOW

Each paid agent/company receives one dedicated messaging number when activation succeeds.

The number is a messaging identity connected to Sent.dm and Chesera. It is not a number the agent logs into manually with WhatsApp or another app.

Inbound message flow:

1. Lead sends SMS, RCS, or WhatsApp.
2. Sent.dm receives the message.
3. Sent.dm sends a webhook to Chesera.
4. Chesera identifies the correct agent/company.
5. Chesera saves the lead, conversation, and message.
6. Chesera AI or the agent creates a reply.
7. Chesera sends the reply through Sent.dm.
8. Sent.dm chooses the best available channel/fallback where appropriate.

## SMS AND 10DLC APPROVAL

For US SMS, 10DLC approval is still required. Sent.dm helps manage this process, but it cannot be skipped.

Expected timing:

- Best case: same day to 1 business day.
- Normal case: 1-3 business days.
- Safe public estimate: 1-3 business days.
- If information is incomplete or rejected, it can take longer.

Approval is not the end of compliance. Registered sample messages must match live traffic. AI prompts must keep replies inside the approved business use case.

## AI MESSAGE COMPLIANCE RULES

AI replies must:

- Identify the business by name in the first message.
- Include STOP opt-out language in the first message.
- Stay inside the approved use case.
- Avoid false urgency or pressure language.
- Avoid ALL CAPS.
- Avoid excessive punctuation.
- Avoid link shorteners.
- Avoid spam-like or unrelated content.
- Stay clear, conversational, and relevant to the lead.

Sample structure:

```text
Hi [Name], this is the assistant for [Agent Business]. Thanks for reaching out about [topic]. Reply STOP to opt out.
```

## WHATSAPP FLOW

WhatsApp is optional for V1.

Default messaging remains SMS/RCS through the Sent.dm-assigned Sender Profile number. Agents who do not have or do not want WhatsApp can still use Chesera through SMS/RCS.

For agents who already have a Meta-approved WhatsApp Business Account/WABA, Chesera can connect that WhatsApp identity to the agent's Sent.dm Sender Profile during onboarding.

Optional WhatsApp fields stored on the business profile:

- `sentdm_whatsapp_waba_id`
- `sentdm_whatsapp_phone_number_id`
- `sentdm_whatsapp_access_token`

Rules:

- All three fields are optional.
- If none are provided, Chesera skips WhatsApp and still allows SMS/RCS setup.
- If any one of the three is provided, all three are required.
- The access token must not be returned in normal API responses.
- During Sender Profile creation, Chesera sends `whatsapp_business_account` to Sent.dm only when all three fields are present.
- If Sent.dm rejects the WhatsApp config, Chesera should show a clear error telling the agent/admin to verify the WABA ID, phone number ID, access token, phone-number ownership, and Meta permissions.

Important architecture decision:

- SMS sender number = Sent.dm-assigned/provisioned Sender Profile number.
- WhatsApp sender number = the Meta/WABA phone number represented by the agent's `phone_number_id`.
- These can be different numbers in V1.

Reason:

Using the Sent.dm-provided SMS/RCS number as the main WhatsApp number would require waiting for Sent.dm number assignment first, then connecting that number through Meta Business/WABA setup and waiting for Meta approval. That creates an extra dependency and can delay activation. Using an already-prepared WhatsApp Business number keeps SMS/RCS activation independent from Meta/WhatsApp setup.

Important rule:

> WhatsApp has Meta's 24-hour customer-service window.

This means:

- If a lead messages the agent on WhatsApp, Chesera can reply freely within 24 hours.
- Every new message from the lead resets the 24-hour window.
- If the window closes, free-form WhatsApp replies are no longer allowed.
- Outside the window, WhatsApp may require approved template messages.

For V1, scheduled follow-ups outside the 24-hour WhatsApp window should route to SMS instead of using WhatsApp templates.
## FOLLOW-UP SEQUENCES

Chesera's planned follow-up sequence:

- Day 1
- Day 3
- Day 7
- Day 14

Decision:

- Route follow-ups outside WhatsApp's 24-hour window to SMS.

Reason:

- Simpler for V1.
- Avoids maintaining many WhatsApp templates per vertical.
- Reduces approval delay.
- Keeps delivery predictable.
- SMS/10DLC is already part of paid activation.

## STOP HELP AND CONSENT HANDLING

Before any AI reply, every inbound message must be checked for compliance keywords.

Opt-out keywords:

```text
STOP
STOPALL
UNSUBSCRIBE
CANCEL
END
QUIT
```

When received:

- Mark the lead permanently opted out in Chesera.
- Close open conversations for that lead.
- Stop future AI replies.
- Stop follow-up sequences.
- Stop campaign/reminder messages.

HELP handling:

- If a lead sends `HELP`, reply with the agent's support email and basic help text.

This opt-out state must be stored inside Chesera even if Sent.dm also tracks it.

## WEBHOOK PROCESSING

Sent.dm webhooks must be handled asynchronously.

Flow:

```text
Sent.dm sends webhook
-> Chesera verifies webhook signature
-> Chesera stores/queues the event
-> Chesera returns 200 immediately
-> background worker processes message
-> AI generates reply
-> Chesera sends reply through Sent.dm
```

Do not call OpenAI inside the webhook request/response cycle. This prevents timeout retries and duplicate replies.

## WEBHOOK SECURITY

Every Sent.dm webhook must be verified before processing.

Expected verification inputs:

- `x-webhook-signature`
- `x-webhook-id`
- `x-webhook-timestamp`
- raw request body
- Sent.dm webhook secret

Verification uses HMAC-SHA256 and timing-safe comparison.

Reject invalid or stale webhook requests before parsing/processing business logic.

## SANDBOX TESTING

Sandbox mode is controlled per request with:

```json
{
  "sandbox": true
}
```

In Django, use an environment switch:

```env
SENTDM_SANDBOX_MODE=True
```

When true, add `sandbox: true` to supported Sent.dm mutation requests.

Sandbox can test:

- API key validity.
- Request shape.
- Sender Profile request shape.
- Campaign request shape.
- Profile completion request shape.
- Message send request shape.
- Local Chesera database/status flow.
- Webhook handler behavior with manually simulated payloads.

Sandbox cannot prove:

- Real number activation.
- Real 10DLC approval.
- Real SMS/RCS/WhatsApp delivery.
- Real inbound carrier/provider webhooks.

Before production rollout, run one controlled live pilot with sandbox disabled.

