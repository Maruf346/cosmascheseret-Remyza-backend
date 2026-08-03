from django.conf import settings
from django.db import transaction
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from business.models import ProviderAccount, PhoneNumber, LocalVerification
from django.utils import timezone
from typing import Any, Dict
from business.choices import PhoneNumberStatus
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
import os

from core.models import MessagingService, A2PBrand, A2PCampaign, CustomerProfile
from core.choices import MessagingServiceStatus
from example import sub_account_create_response, toll_free_number_purchase_response, twilio_messaging_service_response
from core.helper import purchase_to_dict, MessageService_to_Dict, TrustHubPolicy_to_Dict, CustomerProfile_to_Dict

class TwilioService:
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")

    def __init__(self, user, organization=None):
        self.user = user
        self.organization = organization
        self.client = self.master_client()
        self.free_trail_client = self.free_trail_client()

    # ---------------------------------------------------------------------
    # Client
    def master_client(self) -> Client:
        ACCOUNT_SID = os.getenv("ACCOUNT_SID")
        AUTH_TOKEN = os.getenv("AUTH_TOKEN")
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        return client

    def free_trail_client(self) -> Client:
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

    # ---------------------------------------------------------------------
    # Number Search Method
    def twilio_sub_account_create(self, friendly_name) -> dict:
        # live data--------
        # client = self.client
        # sub_account = client.api.accounts.create(
        #     friendly_name=friendly_name
        # )
        # serialize_subaccount = self.serialize_subaccount(sub_account)

        serialize_subaccount = self.demo_serializer_subaccount(friendly_name)
        return serialize_subaccount

    # For Development---
    def demo_serializer_subaccount(self, friendly_name):
        # test demo data------
        serialize_subaccount = {
            'sid': os.getenv("ACCOUNT_SID"),
            'friendly_name': friendly_name,
            'status': 'active',
            'owner_account_sid': os.getenv("OWNER_ACCOUNT_ID_2"),
            'auth_token': os.getenv("AUTH_TOKEN")
        }
        return serialize_subaccount

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

    def save_provider_account(self, sub_account: dict,) -> ProviderAccount:
        return ProviderAccount.objects.create(
            user=self.user,
            organization=self.organization,
            account_sid=sub_account["sid"],
            owner_account_sid=sub_account["owner_account_sid"],
            friendly_name=sub_account["friendly_name"],
            status=sub_account["status"],
            auth_token=sub_account["auth_token"],
            last_synced_at=timezone.now(),
            metadata=sub_account,
        )

    @transaction.atomic
    def get_or_create_subaccount(self) -> ProviderAccount:
        try:
            if hasattr(self.organization, "provider_account"):
                provider_account = self.organization.provider_account
                sub_account_, sub_account_serialize = self.sync_subaccount()

                if sub_account_.status == "active":
                    return provider_account
                else:
                    # account close------
                    sub_account = self.twilio_sub_account_create(self.organization.name)
                    provider_account.account_sid = sub_account["sid"]
                    provider_account.owner_account_sid = sub_account["friendly_name"]
                    provider_account.friendly_name = sub_account["status"]
                    provider_account.status = sub_account["status"]
                    provider_account.auth_token = sub_account["auth_token"]
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

    def sync_subaccount(self) -> ProviderAccount:
        try:
            provider_account = self.organization.provider_account
            subaccount_client = self.subaccount_client()
            sub_account_ = subaccount_client.api.accounts(provider_account.account_sid).fetch()
            sub_account_serialize = self.serialize_subaccount(sub_account_)

            provider_account.last_synced_at=timezone.now()
            provider_account.save(update_fields=["last_synced_at"])
            
            return sub_account_, sub_account_serialize
        except TwilioRestException as e:
            logger.exception(e)
            raise
        except Exception as e:
            logger.exception(e)
            raise

    def update_subaccount(self, friendly_name: str) -> ProviderAccount:
        try:
            provider_account = self.organization.provider_account
            subaccount_client = self.subaccount_client()

            sub_account_ = subaccount_client.api.accounts(provider_account.account_sid).update(friendly_name=friendly_name)
            provider_account.friendly_name = sub_account_.friendly_name
            provider_account.status = sub_account_.status
            provider_account.last_synced_at = timezone.now()
            provider_account.save()
            return provider_account
        except TwilioRestException as e:
            logger.exception(e)
            raise
        except Exception as e:
            logger.exception(e)
            raise

    def update_subaccount_credentials(self, account_sid: str, auth_token: str) -> ProviderAccount:
        try:
            provider_account = self.organization.provider_account
            provider_account.account_sid = account_sid
            provider_account.auth_token = auth_token
            provider_account.last_synced_at = timezone.now()
            provider_account.save()
            return provider_account
        except Exception as e:
            logger.exception(e)
            raise

    def subaccount_close(self):
        provider_account = self.organization.provider_account
        subaccount_client = self.subaccount_client()
        subaccount_client.api.v2010.accounts(provider_account.account_sid).update(
            status="closed"
        )
        # return Response(
        #     {
        #         "success": True,
        #         "message": "Close Sub-Account."
        #     }
        # )
        return
    # ---------------------------------------------------------------------


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

    def advanced_search_numbers(
            self, phone_type="local", area_code=None, contains=None, distance=None, sms_enabled=True,
            # voice_enabled: bool = False, mms_enabled: bool = False,
            exclude_all_address_required=False, limit=5,
    ):
        client = self.subaccount_client()

        if phone_type == "local":
            resource = client.available_phone_numbers("US").local
        elif phone_type == "toll_free":
            resource = client.available_phone_numbers("US").toll_free
        else:
            raise ValueError("phone_type must be 'local' or 'toll_free'.")

        params = {
            "limit": limit,
            "sms_enabled": sms_enabled,
            # "voice_enabled": voice_enabled,
            # "mms_enabled": mms_enabled,
            "exclude_all_address_required": exclude_all_address_required,
        }

        if area_code:
            params["area_code"] = area_code
        if distance:
            params["distance"] = distance
        try:
            numbers = resource.list(**params)
            return [
                self.serialize_search_phone_number(number)
                for number in numbers
            ]
        except TwilioRestException:
            logger.exception("Unable to search available phone numbers.")
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
    # Number Purchase
    @transaction.atomic
    def save_phone_number(self, data):
        phone_number, created = PhoneNumber.objects.update_or_create(
            provider_phone_sid=data["sid"],
            defaults={
                "organization": self.organization,
                "provider": self.organization.provider_account,
                "phone_number": data["phone_number"],
                "country": data.get("country_code", "US"),
                "capabilities": data["capabilities"],
                "configuration": {
                    "friendly_name": data["friendly_name"],
                    "voice_url": data["voice_url"],
                    "sms_url": data["sms_url"],
                    "uri": data["uri"],
                    "account_sid": data["account_sid"],
                    "status_callback": data["status_callback"],
                    "address_requirements": data["address_requirements"],
                },
                "status": PhoneNumberStatus.PENDING,
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
    def purchase_number(self, phone_number, sms_url=WEBHOOK_URL, status_callback=WEBHOOK_URL, voice_url=WEBHOOK_URL):        
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
            # serialize_phone_number = toll_free_number_purchase_response(phone_number, sms_url)
            # print("serialize_phone_number: ", serialize_phone_number)

            save_phone_number = self.save_phone_number(serialize_phone_number)
            # print("save_phone_number: ", save_phone_number)
            return serialize_phone_number
        except TwilioRestException:
            logger.exception("Unable to purchase phone number.")
            raise Exception("Unable to purchase phone number.")

    def sync(self, phone_number=None):
        client = self.subaccount_client()
        self.validate_subaccount_credentials()
        phone  = client.incoming_phone_numbers(phone_number.provider_phone_sid).fetch()
        phone_serializer = purchase_to_dict(phone)
        return phone_serializer

    def update_webhook(self, phone_sid, payload={}):
        client = self.subaccount_client()
        self.validate_subaccount_credentials()
        payload = payload
        number = client.incoming_phone_numbers(phone_sid).update(
            **payload
        )
        return purchase_to_dict(number)

    # ---------------------------------------------------------------------



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

class TwilioLocalVerificationService:
    def __init__(self, user, phone_number, organization=None):
        self.user = user
        self.organization = organization
        self.phone_number = phone_number
        self.number_verification = phone_number.local_verification
        self.client = self.master_client()

    # ---------------------------------------------------------------------
    # Client
    def master_client(self) -> Client:
        ACCOUNT_SID = os.getenv("ACCOUNT_SID")
        AUTH_TOKEN = os.getenv("AUTH_TOKEN")
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        return client

    def free_trail_client(self) -> Client:
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

    def get_policies(self):
        try:
            client = self.client
            policies = client.trusthub.v1.policies.list()
            data = [TrustHubPolicy_to_Dict(policy) for policy in policies]
            logger.info("Fetched %s TrustHub policies.", len(data),)
            return data
        except TwilioRestException:
            logger.exception("Unable to fetch TrustHub Policies.")
            raise

    def get_primary_customer_profile(self):
        try:
            profile = self.client.trusthub.v1.customer_profiles.list()[0]
            data = CustomerProfile_to_Dict(profile)
            logger.info("Primary Customer Profile fetched (%s)", profile.sid,)
            return data
        except TwilioRestException:
            logger.exception("Unable to fetch Primary Customer Profile.")
            raise

    def get_primary_customer_profile_policy_sid(self):
        profile = self.get_primary_customer_profile()
        policy_sid = profile.get("policy_sid")
        if not policy_sid:
            raise Exception("Primary Customer Profile Policy SID not found.")
        return policy_sid
    # ---------------------------------------------------------------------

    # ----------------------------------------------------
    # Messaging Service
    @transaction.atomic
    def create_messaging_service(self):
        try:
            if hasattr(self.organization, "messaging_service"):
                return self.organization.messaging_service

            client = self.subaccount_client()
            # service = client.messaging.v1.services.create(friendly_name=f"{self.organization.name} Messaging Service")
            # service_data = MessageService_to_Dict(service)
            service_data = twilio_messaging_service_response

            print("=========Message Service Create Dict===========")
            print("Message Service Serilalizer: ", service_data)
            print("===============================================")
            
            messaging_service = self.save_messaging_service(service_data)

            logger.info("Messaging Service created successfully (%s)", messaging_service.service_sid,)
            return messaging_service
        except TwilioRestException as exc:
            logger.exception("Unable to create Messaging Service.")
            raise exc

    def save_messaging_service(self, data):
        return MessagingService.objects.update_or_create(
            organization=self.organization,
            defaults={
                "service_sid": data["sid"],
                "friendly_name": data["friendly_name"],
                # "status": data["status"],
                "status": MessagingServiceStatus.ACTIVE,
                "last_synced_at": timezone.now(),
                "metadata": data,
            },
        )[0]
    
    @transaction.atomic
    def update_messaging_service(self, friendly_name=None):
        try:
            messaging_service = self.organization.messaging_service
            client = self.subaccount_client()
            service = client.messaging.v1.services(
                messaging_service.service_sid
            ).update(
                friendly_name=friendly_name or messaging_service.friendly_name,
            )

            service_data = MessageService_to_Dict(service)

            messaging_service.friendly_name = service_data["friendly_name"]
            messaging_service.last_synced_at = timezone.now()
            messaging_service.metadata = service_data

            messaging_service.save(
                update_fields=[
                    "friendly_name",
                    "last_synced_at",
                    "metadata",
                ]
            )

            logger.info(
                "Messaging Service updated successfully (%s)",
                messaging_service.service_sid,
            )

            return messaging_service
        except TwilioRestException as exc:
            logger.exception(
                "Unable to update Messaging Service."
            )
            raise exc

    @transaction.atomic
    def sync_messaging_service(self):
        try:
            messaging_service = self.organization.messaging_service
            client = self.subaccount_client()
            service = client.messaging.v1.services(
                messaging_service.service_sid
            ).fetch()

            service_data = self.serialize_messaging_service(service)
            messaging_service.friendly_name = service_data["friendly_name"]
            messaging_service.last_synced_at = timezone.now()
            messaging_service.metadata = service_data

            messaging_service.save(
                update_fields=[
                    "friendly_name",
                    "last_synced_at",
                    "metadata",
                ]
            )

            logger.info(
                "Messaging Service synced successfully (%s)",
                messaging_service.service_sid,
            )
            return messaging_service
        except TwilioRestException as exc:
            logger.exception(
                "Unable to sync Messaging Service."
            )
            raise exc

    @transaction.atomic
    def attach_phone_number(self):
        try:
            if self.number_verification.messaging_service:
                raise Exception("Message Service already attach.")
                # self.number_verification.messaging_service
            
            messaging_service = self.create_messaging_service()
            client = self.subaccount_client()

            response = client.messaging.v1.services(
                messaging_service.service_sid
            ).phone_numbers.create(
                phone_number_sid=self.phone_number.provider_phone_sid
            )

            # Save relation in local database
            self.number_verification.messaging_service = messaging_service
            self.number_verification.messaging_service_attachment_sid = response.sid
            self.number_verification.save(update_fields=["messaging_service", "messaging_service_attachment_sid"])

            self.phone_number.last_synced_at = timezone.now()
            self.phone_number.save(update_fields=["last_synced_at",])   

            logger.info("Phone number (%s) attached to Messaging Service (%s).", self.phone_number.phone_number, messaging_service.service_sid,)
            return messaging_service
        except TwilioRestException as exc:
            logger.exception("Unable to attach phone number to Messaging Service.")
            raise exc

    @transaction.atomic
    def detach_phone_number(self):
        try:
            messaging_service = self.phone_number.messaging_service
            if messaging_service is None:
                return

            client = self.subaccount_client()
            assignments = client.messaging.v1.services(
                messaging_service.service_sid
            ).phone_numbers.list()

            assignment = next(
                (
                    item
                    for item in assignments
                    if item.phone_number_sid
                    == self.phone_number.provider_phone_sid
                ),
                None,
            )

            if assignment:
                client.messaging.v1.services(
                    messaging_service.service_sid
                ).phone_numbers(assignment.sid).delete()



            # Save relation in local database
            self.number_verification.messaging_service = None
            self.number_verification.messaging_service_attachment_sid = None
            self.number_verification.save(update_fields=["messaging_service", "messaging_service_attachment_sid"])

            self.phone_number.last_synced_at = timezone.now()
            self.phone_number.save(update_fields=["last_synced_at",])   

            logger.info("Phone number (%s) detached from Messaging Service.", self.phone_number.phone_number,)
            return True
        except TwilioRestException as exc:
            logger.exception(
                "Unable to detach phone number."
            )
            raise exc

    @transaction.atomic
    def delete_messaging_service(self):
        try:
            messaging_service = self.organization.messaging_service
            client = self.subaccount_client()

            client.messaging.v1.services(
                messaging_service.service_sid
            ).delete()

            LocalVerification.objects.filter(
                messaging_service=messaging_service
            ).update(
                messaging_service=None,
                messaging_service_attachment_sid=None
            )



            service_sid = messaging_service.service_sid
            messaging_service.delete()

            logger.info("Messaging Service deleted successfully (%s)", service_sid,)
            return True
        except MessagingService.DoesNotExist:
            logger.warning(
                "Messaging Service not found for organization (%s)",
                self.organization.id,
            )
            return False
        except TwilioRestException as exc:
            logger.exception(
                "Unable to delete Messaging Service."
            )
            raise exc

    # ----------------------------------------------------


    # ----------------------------------------------------
    # Brand
    @transaction.atomic
    def create_customer_profile(self):
        try:
            if hasattr(self.organization, "customer_profile"):
                return self.organization.customer_profile

            policy_sid = self.get_primary_customer_profile_policy_sid()
            profile = self.client.trusthub.v1.customer_profiles.create(
                friendly_name=self.organization.name, email=self.organization.email, policy_sid=policy_sid,
            )

            data = CustomerProfile_to_Dict(profile)
            customer_profile = self.save_customer_profile(data)
            logger.info("Customer Profile Created (%s)", customer_profile.profile_sid,)
            return customer_profile
        except TwilioRestException:
            logger.exception(
                "Unable to create Customer Profile."
            )
            raise

    @transaction.atomic
    def save_customer_profile(self, data):
        profile, _ = CustomerProfile.objects.update_or_create(
            organization=self.organization,
            defaults={
                "profile_sid": data["sid"],
                "friendly_name": data["friendly_name"],
                "policy_sid": data.get("policy_sid", ""),
                "email": data.get("email", ""),
                "status": data["status"],
                "metadata": data,
                "last_synced_at": timezone.now(),
            },
        )
        return profile
    
    @transaction.atomic
    def register_brand(self):
        """
        2. Create Business End User
        3. Assign End User
        4. Evaluate Customer Profile
        5. Submit Brand Registration
        6. Save Brand
        """
        profile_policy_sid = self.get_primary_customer_profile_policy_sid()

        # customer_profile = self.create_customer_profile()
        # end_user = self.create_business_end_user()
        # self.assign_end_user( customer_profile.sid, end_user.sid,)

        # self.evaluate_customer_profile(customer_profile.sid,)

        # brand = self.submit_brand_registration(customer_profile.sid,)

        # return self.save_brand(brand,)
        return profile_policy_sid

    def update_brand(self):
        pass

    def sync_brand(self):
        pass

    # ----------------------------------------------------

    # ----------------------------------------------------
    # Campaign
    def register_campaign(self):
        pass

    def update_campaign(self):
        pass

    def sync_campaign(self):
        pass

    def assign_messaging_service(self):
        pass

    def remove_messaging_service(self):
        pass

    # ----------------------------------------------------

    # ----------------------------------------------------
    # High Level Workflow
    @transaction.atomic
    def verify(self):
        """
        Complete Verification Process

        1. Create Messaging Service
        2. Attach Number
        3. Register Brand
        4. Register Campaign
        5. Assign Messaging Service
        """

        messaging_service = self.create_messaging_service()

        self.attach_phone_number()

        brand = self.register_brand()

        campaign = self.register_campaign()

        self.assign_messaging_service()

        return {
            "messaging_service": messaging_service,
            "brand": brand,
            "campaign": campaign,
        }

    def sync(self):
        """
        Sync every verification object.
        """

        return {
            "messaging_service": self.sync_messaging_service(),
            "brand": self.sync_brand(),
            "campaign": self.sync_campaign(),
        }

    def get_status(self):
        """
        Returns overall verification status.
        """
        pass

    # ----------------------------------------------------


