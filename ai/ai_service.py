import json
import os

try:
    import openai
except ImportError:
    openai = None

from django.conf import settings


class AIService:
    def __init__(self):
        if openai:
            openai.api_key = getattr(settings, "OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))

    def build_system_prompt(self, organization=None):
        business_name = self._org_value(organization, "sentdm_legal_name") or self._org_value(organization, "name") or "the business"
        support_email = self._org_value(organization, "sentdm_support_email") or self._org_value(organization, "email") or "the business support email"
        vertical = self._org_value(organization, "sentdm_vertical") or "PROFESSIONAL"
        use_case = self._org_value(organization, "sentdm_messaging_use_case") or "customer care and lead follow-up for opted-in contacts"
        custom_prompt = self._org_ai_prompt(organization)
        tone = self._org_reply_tone(organization)

        prompt = f"""
You are Chesera's AI assistant replying by SMS, RCS, or WhatsApp on behalf of {business_name}.

Business context:
- Business name: {business_name}
- Support email: {support_email}
- Approved vertical: {vertical}
- Approved messaging use case: {use_case}
- Desired tone: {tone}

Compliance rules:
- Stay strictly within the approved messaging use case and vertical.
- The first assistant reply in a conversation must identify the business by name.
- The first assistant reply must include clear opt-out language: Reply STOP to opt out.
- Never reply to STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT, or HELP as a normal conversation. Those are handled by the system before you are called.
- Do not use urgency, pressure, fear, or countdown language.
- Do not use ALL CAPS except for required keywords like STOP or HELP.
- Do not use excessive punctuation.
- Do not use link shorteners.
- Do not make claims, offers, guarantees, or promises outside the business information already provided.
- Keep replies concise, natural, and useful for a lead conversation.
- If the lead is ready to buy, book, schedule, or asks for a human, set stage to HOT.
- If the lead is interested but still comparing or asking questions, set stage to WARM.
- Otherwise set stage to COLD.

Return only a valid JSON object using this exact shape:
{{"reply": "...", "stage": "COLD|WARM|HOT"}}
""".strip()

        if custom_prompt:
            prompt += f"\n\nAdditional business instructions:\n{custom_prompt}"
        return prompt

    def generate_reply_and_stage(self, conversation_history, organization=None) -> dict:
        """
        Calls the LLM with the conversation history.
        The response must be JSON containing reply and COLD/WARM/HOT stage.
        """
        system_prompt = self.build_system_prompt(organization=organization)
        messages = [{"role": "system", "content": system_prompt}]

        for msg in list(conversation_history)[-10:]:
            role = "user" if str(msg.direction).lower() == "inbound" else "assistant"
            messages.append({"role": role, "content": msg.content})

        try:
            if openai is None:
                raise RuntimeError("OpenAI SDK is not installed.")
            response = openai.ChatCompletion.create(
                model=self._org_model_name(organization),
                messages=messages,
                temperature=float(self._org_ai_value(organization, "temperature", 0.30)),
                max_tokens=int(self._org_ai_value(organization, "max_tokens", 1000)),
                top_p=float(self._org_ai_value(organization, "top_p", 1.00)),
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            parsed = json.loads(content)

            stage_str = str(parsed.get("stage", "COLD")).upper()
            if stage_str not in ["COLD", "WARM", "HOT"]:
                stage_str = "COLD"

            return {
                "reply": str(parsed.get("reply", "")).strip(),
                "stage": stage_str,
            }
        except Exception:
            business_name = self._org_value(organization, "sentdm_legal_name") or self._org_value(organization, "name") or "The business"
            return {
                "reply": f"{business_name}: Thanks for reaching out. A team member will follow up when available. Reply STOP to opt out.",
                "stage": "HOT",
            }


    def generate_structured_message(self, *, tone, msg) -> dict:
        tone = str(tone or "professional").strip().lower()
        source_message = str(msg or "").strip()
        if not source_message:
            return {"structured_msg": "", "tone": tone}

        messages = [
            {
                "role": "system",
                "content": (
                    "You rewrite short business messages for Chesera users. "
                    "Return only JSON with key structured_msg. Keep the original meaning, make the message clear, natural, compliant, and concise. "
                    "Do not add unsupported promises, urgency pressure, excessive punctuation, ALL CAPS, or shortened links."
                ),
            },
            {"role": "user", "content": f"Tone: {tone}\nMessage: {source_message}"},
        ]
        try:
            if openai is None:
                raise RuntimeError("OpenAI SDK is not installed.")
            response = openai.ChatCompletion.create(
                model=getattr(settings, "OPENAI_STRUCTURED_MESSAGE_MODEL", "gpt-4o"),
                messages=messages,
                temperature=0.35,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            parsed = json.loads(content)
            structured_msg = str(parsed.get("structured_msg", "")).strip()
            if structured_msg:
                return {"structured_msg": structured_msg, "tone": tone}
        except Exception:
            pass

        cleaned = " ".join(source_message.split())
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."
        return {"structured_msg": cleaned, "tone": tone}
    def _org_value(self, organization, field_name, default=""):
        if not organization:
            return default
        value = getattr(organization, field_name, default)
        return str(value).strip() if value not in (None, "") else default

    def _org_ai_config(self, organization):
        if not organization:
            return None
        return getattr(organization, "ai_configuration", None)

    def _org_ai_value(self, organization, field_name, default):
        ai_config = self._org_ai_config(organization)
        if not ai_config:
            return default
        value = getattr(ai_config, field_name, default)
        return value if value not in (None, "") else default

    def _org_ai_prompt(self, organization):
        ai_config = self._org_ai_config(organization)
        if not ai_config:
            return ""
        return str(getattr(ai_config, "system_prompt", "") or "").strip()

    def _org_model_name(self, organization):
        return str(self._org_ai_value(organization, "model_name", "gpt-4o") or "gpt-4o")

    def _org_reply_tone(self, organization):
        if not organization:
            return "friendly and professional"
        settings_obj = getattr(organization, "settings", None)
        tone = getattr(settings_obj, "reply_tone", "") if settings_obj else ""
        return str(tone or "friendly and professional")