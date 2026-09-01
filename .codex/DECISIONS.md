# PROJECT DECISIONS

## SENT.DM AS PRIMARY NEW MESSAGING PROVIDER

Decision:

- Use Sent.dm for new SMS/RCS/WhatsApp messaging work.
- Keep Twilio code untouched during sandbox/proof phase.

Reason:

- One API covers SMS, RCS, and WhatsApp.
- Sender Profiles map cleanly to one paid agent/company per messaging identity.
- Sandbox mode allows safe request-shape testing.
- Sent.dm can handle channel routing/fallback.

## ONE SENDER PROFILE PER PAID AGENT

Decision:

- Chesera has one Sent.dm organization account.
- Each paid agent/company gets one Sent.dm Sender Profile.
- Free users do not get Sender Profiles by default.

Reason:

- Isolates tenants.
- Keeps agents out of Sent.dm.
- Lets Chesera control billing and provisioning.

## ACTIVATION TIMELINE

Decision:

- Use `1-3 business days` as the public activation estimate.
- Do not promise instant messaging activation.

Reason:

- US SMS requires 10DLC approval.
- Sender Profile and number setup can be quick, but production sendability depends on approval/configuration.

## WHATSAPP FOLLOW-UP ROUTING

Decision:

- Route scheduled follow-ups outside Meta's 24-hour WhatsApp window to SMS for V1.

Reason:

- Avoids WhatsApp template complexity.
- Faster V1.
- More predictable follow-up delivery.
- SMS/10DLC is already part of the paid activation flow.

## SANDBOX LIMITATION

Decision:

- Use sandbox for development and request validation.
- Require one controlled live pilot before production rollout.

Reason:

- Sandbox does not create real profiles, submit real 10DLC campaigns, activate real numbers, or send real messages.

## WEBHOOKS MUST BE ASYNC AND VERIFIED

Decision:

- Sent.dm webhook handlers must verify signatures before processing.
- Webhook handlers should queue processing and return 200 immediately.

Reason:

- Prevents fake message injection.
- Avoids provider retries and duplicate AI replies caused by slow OpenAI responses.


## OPTIONAL PER-AGENT WHATSAPP WABA

Decision:

- WhatsApp is optional in V1.
- SMS/RCS remains the default messaging path through the Sent.dm-assigned Sender Profile number.
- Agents who already have a Meta-approved WhatsApp Business Account/WABA can connect it during Chesera onboarding.
- Chesera stores `sentdm_whatsapp_waba_id`, `sentdm_whatsapp_phone_number_id`, and `sentdm_whatsapp_access_token` on the business profile.
- Chesera sends `whatsapp_business_account` to Sent.dm only when all three values are present.
- The access token is write-only in normal API serializers and must not be returned in responses.

Reason:

- Using the Sent.dm-provided SMS/RCS number as the WhatsApp sender would require waiting for number assignment, then Meta/WABA setup and approval, which can delay activation.
- Keeping WhatsApp optional lets SMS/RCS activate independently.
- Agents with an existing WhatsApp Business API setup can still use their own WhatsApp identity through Sent.dm.
