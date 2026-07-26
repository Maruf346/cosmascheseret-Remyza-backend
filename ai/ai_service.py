import os
import json
import openai
from django.conf import settings
from communications.models import Message
from crm.models import LeadStage

class AIService:
    def __init__(self):
        openai.api_key = getattr(settings, 'OPENAI_API_KEY', os.getenv("OPENAI_API_KEY"))

    def generate_reply_and_stage(self, conversation_history) -> dict:
        """
        Calls the LLM with the conversation history.
        Instructs the LLM to return a JSON object containing the 'reply' and the 'stage'.
        """
        system_prompt = (
            "You are a helpful AI customer support agent. "
            "Based on the user's messages, you must generate a helpful response AND "
            "evaluate their temperature/stage (COLD, WARM, or HOT). "
            "HOT means they are ready to buy or urgently need human assistance. "
            "Respond strictly in JSON format: {'reply': '...', 'stage': 'COLD|WARM|HOT'}"
        )

        messages = [{"role": "system", "content": system_prompt}]
        
        # Add history
        # Expecting Django queryset or list of Message objects
        # We take the last 10 messages for context
        for msg in list(conversation_history)[-10:]:
            role = "user" if msg.direction == "INBOUND" else "assistant"
            messages.append({"role": role, "content": msg.content})

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o", # Can be configured via settings
                messages=messages,
                response_format={ "type": "json_object" }
            )
            content = response.choices[0].message.content
            parsed = json.loads(content)
            
            # Map string to LeadStage choices if needed, but the strings COLD/WARM/HOT match the defaults
            stage_str = parsed.get("stage", "COLD").upper()
            if stage_str not in ["COLD", "WARM", "HOT"]:
                stage_str = "COLD"
            
            return {
                "reply": parsed.get("reply", ""),
                "stage": stage_str
            }
        except Exception as e:
            # Fallback or error handling
            return {"reply": "I'm sorry, I am having trouble connecting right now. A human agent will be with you shortly.", "stage": "HOT"}
