from django.http import HttpResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from twilio.twiml.messaging_response import MessagingResponse
from business.models import PhoneNumber
from crm.models import Lead, LeadStage
from communications.models import Conversation, Message
from ai.ai_service import AIService
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def twilio_sms_webhook(request: HttpRequest):
    """
    Endpoint to receive incoming SMS payloads from Twilio.
    URL should be configured in the Twilio Phone Number's webhook settings.
    """
    incoming_msg = request.POST.get('Body', '')
    from_number = request.POST.get('From', '')
    to_number = request.POST.get('To', '') # The SaaS Client's Twilio Number
    twilio_message_sid = request.POST.get('MessageSid', '')

    try:
        # 1. Identify the Client's Phone Number and Organization
        client_phone = PhoneNumber.objects.filter(phone_number=to_number).first()
        if not client_phone:
            logger.error(f"Received SMS to unknown number: {to_number}")
            return HttpResponse("Number not found", status=404)

        organization = client_phone.organization

        # 2. Identify or Create the Customer (Lead)
        lead, _ = Lead.objects.get_or_create(
            organization=organization,
            contact_number=from_number,
            defaults={'business_phone': client_phone}
        )

        # 3. Identify or Create the Conversation
        conversation = Conversation.objects.filter(
            organization=organization,
            lead=lead,
            status='ACTIVE'
        ).first()

        if not conversation:
            conversation = Conversation.objects.create(
                organization=organization,
                lead=lead,
                status='ACTIVE'
            )

        # 4. Store Incoming Message
        Message.objects.create(
            lead=lead,
            conversation=conversation,
            direction='INBOUND',
            sender=from_number,
            recipient=to_number,
            content=incoming_msg,
            provider_message_sid=twilio_message_sid,
            status='DELIVERED'
        )

        # 5. Check for Human Handoff flag (ai_enabled)
        if not lead.ai_enabled or not conversation.ai_enabled:
            # AI is paused. Just store the message. 
            # Return empty 200 so Twilio knows we received it but don't auto-reply.
            return HttpResponse(status=200)

        # 6. AI Processing
        history = conversation.messages.order_by('created_at')
        ai_service = AIService()
        ai_response = ai_service.generate_reply_and_stage(history)

        reply_text = ai_response.get('reply', '')
        new_stage_str = ai_response.get('stage', 'COLD')

        # 7. Update Stage and Handoff Logic
        # Map string to LeadStage if necessary, but assume they match
        new_stage = getattr(LeadStage, new_stage_str.upper(), LeadStage.COLD)
        lead.stage = new_stage
        
        if new_stage == LeadStage.HOT:
            lead.ai_enabled = False
            conversation.ai_enabled = False
            conversation.save()
            # TODO: Trigger Push Notification to the client's app (alerting of hot lead)
            
        lead.save()

        # 8. Store Outgoing Message
        Message.objects.create(
            lead=lead,
            conversation=conversation,
            direction='OUTBOUND',
            sender=to_number,
            recipient=from_number,
            content=reply_text,
            is_ai_generated=True,
            status='SENT' # Assume sent as we are returning TwiML
        )

        # 9. Send Reply via Twilio (Using TwiML for synchronous reply via Webhook)
        resp = MessagingResponse()
        resp.message(reply_text)
        return HttpResponse(str(resp), content_type='text/xml')

    except Exception as e:
        logger.exception("Error processing Twilio Webhook")
        return HttpResponse(status=500)
