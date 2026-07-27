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

    def free_trail_client(self):
        FREE_TRAIL_ACCOUNT_SID = os.getenv("FREE_TRAIL_ACCOUNT_SID")
        FREE_TRAIL_AUTH_TOKEN = os.getenv("FREE_TRAIL_AUTH_TOKEN")
        client = Client(FREE_TRAIL_ACCOUNT_SID, FREE_TRAIL_AUTH_TOKEN)
        return client

    def subaccount_client(self) -> Client:
        provider = self.organization.provider_account
        return Client(
            provider.account_sid,
            provider.auth_token,
        )
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

    def search_numbers(self, phone_type, country="US", area_code=None, sms_enabled=True, limit=2,):
        client = self.free_trail_client()
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
    # ---------------------------------------------------------------------



    # For Production---
    def serialize_subaccount(self, sub_account):
        return {
            "sid": sub_account.sid,
            "friendly_name": sub_account.friendly_name,
            "status": sub_account.status,
            "owner_account_sid": sub_account.owner_account_sid,
            # "date_created": sub_account.date_created,
            "auth_token": sub_account.auth_token,
        }

    # For Development---
    def demo_serializer_subaccount(self):
        # test demo data------
        serialize_subaccount = {
            'sid': os.getenv("SID_2"),
            'friendly_name': 'Safa World',
            'status': 'active',
            'owner_account_sid': os.getenv("OWNER_ACCOUNT_ID_2"),
            'auth_token': os.getenv("AUTH_TOKEN_2")
        }
        return serialize_subaccount


    def twilio_sub_account_create(self, friendly_name) -> dict:
        # live data--------
        # client = self.client
        # sub_account = client.api.accounts.create(
        #     friendly_name=friendly_name
        # )
        # serialize_subaccount = self.serialize_subaccount(sub_account)

        serialize_subaccount = self.demo_serializer_subaccount()
        print("serialize_subaccount: ", serialize_subaccount)
        
        return serialize_subaccount

    def save_provider_account(self, sub_account: dict,) -> ProviderAccount:
        return ProviderAccount.objects.create(
            organization=self.organization,
            account_sid=sub_account["sid"],
            owner_account_sid=sub_account["owner_account_sid"],
            friendly_name=sub_account["friendly_name"],
            status=sub_account["status"],
            auth_token=sub_account["auth_token"],
            last_synced_at=timezone.now,
            metadata=sub_account,
        )

    @transaction.atomic
    def get_or_create_subaccount(self) -> ProviderAccount:
        try:
            if hasattr(self.organization, "provider_account"):
                provider_account = self.organization.provider_account
                subaccount_client = self.subaccount_client()
                sub_account_status = subaccount_client.api.accounts(provider_account.account_sid).fetch()
                if sub_account_status.status == "active":
                    provider_account.last_synced_at = timezone.now()
                    provider_account.save()
                    return provider_account
                else:
                    sub_account = self.twilio_sub_account_create(self.organization.name)
                    provider_account.account_sid = sub_account["sid"]
                    provider_account.owner_account_sid = sub_account["friendly_name"]
                    provider_account.friendly_name = sub_account["status"]
                    provider_account.status = sub_account["status"]
                    provider_account.auth_token = sub_account["auth_token"]
                    provider_account.last_synced_at = timezone.now()
                    provider_account.save()
                    return provider_account
            else:
                sub_account = self.twilio_sub_account_create(self.organization.name)
                provider_account = self.save_provider_account(sub_account)
                return provider_account
        except TwilioRestException as e:
            logger.exception(e)
            raise
        except Exception as e:
            logger.exception(e)
            raise
    

    def validate_master_credentials(self) -> bool:
        try:
            account = self.client.api.accounts(
                settings.TWILIO_ACCOUNT_SID
            ).fetch()
            logger.info(
                "Twilio master account validated successfully (%s)",
                account.sid,
            )
            return True
        except TwilioRestException as exc:
            logger.exception("Twilio master credential validation failed.")

            raise exc

    def validate_subaccount_credentials(self) -> bool:
        provider = getattr(self.organization, "provider_account", None)
        if provider is None:
            raise ValueError("Organization has no ProviderAccount.")
        client = self.subaccount_client()
        try:
            account = client.api.accounts(
                provider.account_sid
            ).fetch()
            logger.info(
                "Twilio subaccount validated successfully (%s)",
                account.sid,
            )
            return True
        except TwilioRestException as exc:
            logger.exception(
                "Twilio subaccount credential validation failed."
            )
            raise exc
    

    

    
    
    def advanced_search_numbers( self, country: str = "US", phone_type: str = "local", area_code: str | None = None, contains: str | None = None, in_region: str | None = None, in_locality: str | None = None, near_number: str | None = None, near_lat_long: tuple | None = None, distance: int | None = None, sms_enabled: bool = True, voice_enabled: bool = False, mms_enabled: bool = False, fax_enabled: bool = False, exclude_all_address_required: bool = False, limit: int = 20,):
        client = self.subaccount_client()
        if phone_type == "local":
            resource = client.available_phone_numbers(country).local

        elif phone_type == "toll_free":
            resource = client.available_phone_numbers(country).toll_free

        else:
            raise ValueError(
                "phone_type must be 'local' or 'toll_free'."
            )

        params = {
            "limit": limit,
            "sms_enabled": sms_enabled,
            "voice_enabled": voice_enabled,
            "mms_enabled": mms_enabled,
            "fax_enabled": fax_enabled,
            "exclude_all_address_required": exclude_all_address_required,
        }

        if area_code:
            params["area_code"] = area_code

        if contains:
            params["contains"] = contains

        if in_region:
            params["in_region"] = in_region

        if in_locality:
            params["in_locality"] = in_locality

        if near_number:
            params["near_number"] = near_number

        if near_lat_long:

            latitude, longitude = near_lat_long

            params["near_lat_long"] = f"{latitude},{longitude}"

        if distance:
            params["distance"] = distance

        try:

            return resource.list(**params)

        except TwilioRestException:

            logger.exception(
                "Unable to search available phone numbers."
            )

            raise
    
    def subaccount_close(self):
        # ACCOUNT_SID = os.getenv("ACCOUNT_SID")
        # AUTH_TOKEN = os.getenv("AUTH_TOKEN")
        # client = Client(ACCOUNT_SID, AUTH_TOKEN)
        # client.api.v2010.accounts("ACCOUNT_SID").update(
        #     status="closed"
        # )
        # return Response(
        #     {
        #         "success": True,
        #         "message": "Close Sub-Account."
        #     }
        # )
        return

    
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

    def serialize_purchase_phone_number(self, phone) -> Dict[str, Any]:
        return {
            "sid": getattr(phone, "sid", None),
            "account_sid": getattr(phone, "account_sid", None),
            "friendly_name": getattr(phone, "friendly_name", None),
            "phone_number": getattr(phone, "phone_number", None),
            "country_code": getattr(phone, "iso_country", None),
            "capabilities": getattr(phone, "capabilities", {}),
            "voice_url": getattr(phone, "voice_url", None),
            "sms_url": getattr(phone, "sms_url", None),
            "status_callback": getattr(phone, "status_callback", None),
            "address_requirements": getattr(phone, "address_requirements", None),
            "date_created": getattr(phone, "date_created", None),
            "date_updated": getattr(phone, "date_updated", None),
            "uri": getattr(phone, "uri", None),
        }

    @transaction.atomic
    def purchase_number(self, phone_number: str, sms_url: str | None = None, status_callback: str | None = None, voice_url: str | None = None,):        
        client = self.subaccount_client()
        payload = {"phone_number": phone_number,}

        if sms_url:
            payload["sms_url"] = sms_url
        if status_callback:
            payload["status_callback"] = status_callback
        if voice_url:
            payload["voice_url"] = voice_url

        try:
            purchased = client.incoming_phone_numbers.create(**payload)
            print("purchased: ", purchased)
            logger.info("Phone number purchased successfully (%s)", purchased.phone_number,)

            serialize_phone_number = self.serialize_purchase_phone_number(purchased)
            print("serialize_phone_number: ", serialize_phone_number)

            save_phone_number = self.save_phone_number(serialize_phone_number)
            print("save_phone_number: ", save_phone_number)
            return serialize_phone_number
        except TwilioRestException:
            logger.exception("Unable to purchase phone number.")
            raise Exception("Unable to purchase phone number.")


    def list_numbers(self, country="US", phone_type="local", area_code=None, sms_enabled=True, limit=20,):
        client = self.subaccount_client()
        if phone_type == "local":
            resource = client.available_phone_numbers(country).local
        elif phone_type == "toll_free":
            resource = client.available_phone_numbers(country).toll_free
        else:
            raise ValueError("Unsupported phone type.")
        numbers = resource.list(limit=2, sms_enabled=True)
        return [
            self.serialize_search_phone_number(number)
            for number in numbers
        ]

    def release_number(self, phone_sid: str):
        client = self.subaccount_client()
        try:
            client.incoming_phone_numbers(phone_sid).delete()
            PhoneNumber.objects.filter(
                sid=phone_sid,
                organization=self.organization,
            ).update(
                is_active=False,
            )

            return True

        except TwilioRestException:
            logger.exception("Failed to release phone number.")
            raise
    
    def update_webhook(
        self,
        phone_sid: str,
        sms_url: str = None,
        voice_url: str = None,
    ):
        client = self.subaccount_client()

        payload = {}

        if sms_url:
            payload["sms_url"] = sms_url
            payload["sms_method"] = "POST"

        if voice_url:
            payload["voice_url"] = voice_url
            payload["voice_method"] = "POST"

        number = client.incoming_phone_numbers(phone_sid).update(
            **payload
        )

        return self.serialize_phone_number(number)

