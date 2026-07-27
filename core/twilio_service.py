from django.conf import settings
from django.db import transaction
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from business.models import ProviderAccount, PhoneNumber
from django.utils import timezone
from typing import Any, Dict
from business.choices import PhoneNumberStatus
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
import os

from .models import FreeTrailPhoneNumber



class TwilioService:
    def __init__(self, organization=None):
        self.organization = organization
        self.client = self.master_client()
        self.free_trail_client = self.free_trail_client()

    # ---------------------------------------------------------------------
    # Client
    def master_client(self):
        ACCOUNT_SID = os.getenv("ACCOUNT_SID")
        AUTH_TOKEN = os.getenv("AUTH_TOKEN")
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        return client

    def free_trail_client(self) -> Client:
        FREE_TRAIL_ACCOUNT_SID = os.getenv("FREE_TRAIL_ACCOUNT_SID")
        FREE_TRAIL_AUTH_TOKEN = os.getenv("FREE_TRAIL_AUTH_TOKEN")
        client = Client(FREE_TRAIL_ACCOUNT_SID, FREE_TRAIL_AUTH_TOKEN)
        return client

    def organization_client(self) -> Client:
        provider = self.organization.provider_account
        return Client(
            provider.account_sid,
            provider.auth_token,
        )

    def user_client(self, organization):
        sub_account = getattr(organization, "provider_account", None)
        if sub_account:
            return Client(
                sub_account.account_sid,
                sub_account.auth_token,
            )
        else:
            raise Exception("Sub Account Not Found")

    # ---------------------------------------------------------------------

    # ---------------------------------------------------------------------
    # Number Search Method
    def serialize_search_phone_number(self, number):
        return {
            "friendly_name": number.friendly_name,
            "phone_number": number.phone_number,
            "lata": getattr(number, "lata", None),
            "rate_center": getattr(number, "rate_center", None),
            "region": getattr(number, "region", None),
            "postal_code": getattr(number, "postal_code", None),
            "locality": getattr(number, "locality", None),
            "iso_country": getattr(number, "iso_country", None),
            "capabilities": number.capabilities,
            "address_requirements": number.address_requirements,
        }

    def search_numbers(self, phone_type, search=None, country="US", area_code=None, sms_enabled=True, limit=2,):
        client = self.master_client()
        try:
            if phone_type == "local":
                resource = client.available_phone_numbers(country).local
            elif phone_type == "toll_free":
                resource = client.available_phone_numbers(country).toll_free
            else:
                raise ValueError("Unsupported phone type.")
            
            params = {
                "limit": limit,
                "sms_enabled": sms_enabled,
            }
            if area_code:
                params["area_code"] = area_code
            numbers = resource.list(**params)
            return [
                self.serialize_search_phone_number(number)
                for number in numbers
            ]
        except TwilioRestException:
            logger.exception("Unable to search phone numbers.")
            raise

    def check_availability(self, phone_type, contains, country="US"):
        client = self.master_client()
        try:
            if phone_type == "local":
                resource = client.available_phone_numbers(country).local.list(contains=contains)
            elif phone_type == "toll_free":
                resource = client.available_phone_numbers(country).toll_free.list(contains=contains)
            else:
                raise ValueError("Unsupported phone type.")

            # numbers = resource.list(contains=contains)
            return [
                self.serialize_search_phone_number(number)
                for number in resource
            ]
        except TwilioRestException:
            logger.exception("Unable to search phone numbers.")
            raise
    # ---------------------------------------------------------------------

    # ---------------------------------------------------------------------
    # Number Purchase Method
    @transaction.atomic
    def save_phone_number(self, data):
        phone_number, created = PhoneNumber.objects.update_or_create(
            provider_phone_sid=data["sid"],
            defaults={
                "organization": self.organization,
                "provider": self.organization.provider_account,
                "phone_number": data["phone_number"],
                "country": data["country_code"],
                "capabilities": data["capabilities"],
                "configuration": {
                    "friendly_name": data["friendly_name"],
                    "voice_url": data["voice_url"],
                    "sms_url": data["sms_url"],
                    "uri": data["uri"],
                    "account_sid": data["account_sid"],
                },
                "status": PhoneNumberStatus.ACTIVE,
                "purchased_at": timezone.now(),
                "last_synced_at": timezone.now(),
            },
        )

        logger.info(
            "Phone number synced successfully (%s)",
            phone_number.phone_number,
        )
        return phone_number

    def save_free_trail_number(self, data):
        free_trail_phone_number, created = FreeTrailPhoneNumber.objects.update_or_create(
        provider_phone_sid=data["sid"],
        phone_number=data["phone_number"],
        defaults={
            "owner_account_sid": self.MASTER_ACCOUNT_SID,
            "account_sid": self.FREE_TRAIL_ACCOUNT_SID,
            "account_auth_token": self.FREE_TRAIL_AUTH_TOKEN,
            "capabilities": data["capabilities"],
            "metadata": data,
            "status": PhoneNumberStatus.ACTIVE,

            "purchased_at": data["date_created"],
            "last_synced_at": data["date_updated"],
            "is_used": False,
            "webhook_url": data["sms_url"] or "",
        },
    )

    def purchase_free_trail_number(self, phone_number):
        from .helper import purchase_to_dict
        try:
            client = self.free_trail_client()
        except:
            client = self.master_client()

        payload = {"phone_number": phone_number,}
        purchased = client.incoming_phone_numbers.create(**payload)
        logger.info("Phone number purchased successfully (%s)", purchased.phone_number,)
        serialize_phone_number = purchase_to_dict(purchased)

        free_trail_number = self.save_free_trail_number(serialize_phone_number)
        return serialize_phone_number

    @transaction.atomic
    def purchase_number(self, phone_number: str, user=None, sms_url: str | None = None, status_callback: str | None = None, voice_url: str | None = None,):
        from .helper import purchase_to_dict
        from accounts.choices import UserType

        organization = getattr(user, "organization", None)
        if not organization:
            raise Exception("User Business Profile not Found.")
        client = self.user_client(user.organization)
        payload = {"phone_number": phone_number,}

        if sms_url:
            payload["sms_url"] = sms_url
        if status_callback:
            payload["status_callback"] = status_callback
        if voice_url:
            payload["voice_url"] = voice_url
        try:
            purchased = client.incoming_phone_numbers.create(**payload)
            logger.info("Phone number purchased successfully (%s)", purchased.phone_number,)

            serialize_phone_number = purchase_to_dict(purchased)

            save_phone_number = self.save_phone_number(serialize_phone_number)
            return serialize_phone_number
        except TwilioRestException:
            logger.exception("Unable to purchase phone number.")
            raise Exception("Unable to purchase phone number.")

    # ---------------------------------------------------------------------
    


