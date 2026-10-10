WELCOME_MESSAGE_TEMPLATES = {
    "professional": {
        "key": "professional",
        "label": "Professional",
        "subject": "Professional Welcome Message",
        "message": "Hello [Name], this is [Business Name]. Thank you for contacting us. Please share what you need help with, and we will guide you from here. Reply STOP to opt out.",
        "tone": "Polished, respectful, and business-focused.",
    },
    "friendly": {
        "key": "friendly",
        "label": "Friendly",
        "subject": "Friendly Welcome Message",
        "message": "Hi [Name], thanks for reaching out to [Business Name]. We are happy to help. Tell us a little more about what you are looking for. Reply STOP to opt out.",
        "tone": "Warm, approachable, and helpful.",
    },
    "casual": {
        "key": "casual",
        "label": "Casual",
        "subject": "Casual Welcome Message",
        "message": "Hey [Name], you reached [Business Name]. Thanks for the message. What can we help you with today? Reply STOP to opt out.",
        "tone": "Relaxed, direct, and conversational.",
    },
}


def get_welcome_template(template_key):
    key = (template_key or "").strip().lower()
    return WELCOME_MESSAGE_TEMPLATES.get(key)


def list_welcome_templates():
    return list(WELCOME_MESSAGE_TEMPLATES.values())
