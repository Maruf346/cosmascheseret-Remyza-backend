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


from example import toll_free_number_purchase_response
from .helper import purchase_to_dict, TFV_to_dict
from .choices import VerificationStatus
from business.choices import PhoneNumberStatus
from .models import TollFreeVerification
from django.utils import timezone

class TwilioService:
    FREE_TRAIL_ACCOUNT_SID = os.getenv("FREE_TRAIL_ACCOUNT_SID")
    FREE_TRAIL_AUTH_TOKEN = os.getenv("FREE_TRAIL_AUTH_TOKEN")

    MASTER_ACCOUNT_SID = os.getenv("ACCOUNT_SID")
    MASTER_AUTH_TOKEN = os.getenv("AUTH_TOKEN")

    def __init__(self, organization=None):
        self.organization = organization
        self.client = self.master_client()
        self.free_trail_client = self.free_trail_client()

    # ---------------------------------------------------------------------
    # Client
    def master_client(self) -> Client:
        client = Client(self.MASTER_ACCOUNT_SID, self.MASTER_AUTH_TOKEN)
        return client

    def free_trail_client(self) -> Client:
        client = Client(self.FREE_TRAIL_ACCOUNT_SID, self.FREE_TRAIL_AUTH_TOKEN)
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

    def get_object_client(self, object: FreeTrailPhoneNumber):
        return Client(object.account_sid, object.account_auth_token)

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

    def validate_client_credentials(self, client, object):
        try:
            account = client.api.accounts(
                object.account_sid
            ).fetch()
            logger.info(
                "Twilio master account validated successfully (%s)",
                account.sid,
            )
            return True
        except TwilioRestException as exc:
            logger.exception("Twilio master credential validation failed.")

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
            # if area_code:
            #     params["area_code"] = area_code
            # numbers = resource.list(**params)
            numbers = resource.list(limit=limit, sms_enabled=True)
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
                "account_sid": data["sid"],
                "account_auth_token": self.MASTER_AUTH_TOKEN,
                "capabilities": data["capabilities"],
                "metadata": data,
                "status": PhoneNumberStatus.ACTIVE,

                "purchased_at": data["date_created"],
                "last_synced_at": data["date_updated"],
                "is_used": False,
                "webhook_url": data["sms_url"] or "",
            },
        )
        logger.info(
            "Phone number synced successfully (%s)",
            free_trail_phone_number.phone_number,
        )
        return free_trail_phone_number

    def purchase_free_trail_number(self, phone_number):
        try:
            client = self.free_trail_client()
        except:
            client = self.master_client()

        # payload = {"phone_number": phone_number,}
        # purchased = client.incoming_phone_numbers.create(**payload)
        # purchased = toll_free_number_purchase_response()
        # logger.info("Phone number purchased successfully (%s)", purchased.phone_number,)
        # serialize_phone_number = purchase_to_dict(purchased)
        logger.info("Phone number purchased successfully (%s)", phone_number,)
        serialize_phone_number = toll_free_number_purchase_response(phone_number)

        free_trail_number = self.save_free_trail_number(serialize_phone_number)
        return free_trail_number

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

    # ---------------------------------------------------------------------
    # Number Related Method
    def release_number(self, object):
        client = self.get_object_client(object)
        self.validate_client_credentials(client, object)
        try:
            client.incoming_phone_numbers(object.provider_phone_sid).delete()
            return True
        except TwilioRestException:
            logger.exception("Failed to release phone number.")
            raise Exception("Failed to release phone number.")

    def sync(self, object):
        client = self.get_object_client(object)
        self.validate_client_credentials(client, object)

        phone  = client.incoming_phone_numbers(object.provider_phone_sid).fetch()
        phone_serializer = purchase_to_dict(phone)
        return phone_serializer

    # ---------------------------------------------------------------------

    # ---------------------------------------------------------------------
    # Toll Free TFV Verification Related Method
    def update_phone_number_status(self, phone_number, remote):
        print("phone_number: ", phone_number)
        status = (remote.status or "").upper()
        print("status: ", status)
        if status == "TWILIO_APPROVED":
            phone_number.status = PhoneNumberStatus.ACTIVE
        elif status == "TWILIO_REJECTED":
            phone_number.status = PhoneNumberStatus.VERIFICATION_REJECTED
        elif status == "IN_REVIEW":
            phone_number.status = PhoneNumberStatus.VERIFICATION_REVIEW
        else:
            phone_number = PhoneNumberStatus.VERIFICATION_PENDING
        phone_number.last_synced_at = timezone.now()
        phone_number.save(update_fields=["status", "last_synced_at"])
        return phone_number

    def update_tfv_model(self, phone_number, local_tfv, remote):
        convert_dict = TFV_to_dict(remote)
        status = (remote.status or "").upper()

        # Twilio
        local_tfv.customer_profile_sid = remote.customer_profile_sid
        local_tfv.tollfree_phone_number_sid = remote.tollfree_phone_number_sid
        local_tfv.verification_sid = remote.sid
        local_tfv.external_reference_id = remote.external_reference_id

        local_tfv.business_name = remote.business_name
        local_tfv.doing_business_as = remote.doing_business_as or local_tfv.doing_business_as
        local_tfv.business_website = remote.business_website or local_tfv.business_website
        local_tfv.notification_email = remote.notification_email or local_tfv.notification_email

        local_tfv.business_registration_number = remote.business_registration_number or local_tfv.business_registration_number
        local_tfv.business_registration_authority = remote.business_registration_authority or local_tfv.business_registration_authority
        local_tfv.business_registration_country = remote.business_registration_country or local_tfv.business_registration_country
        local_tfv.business_registration_phone_number = remote.business_contact_phone or local_tfv.business_registration_phone_number
        local_tfv.business_type = remote.business_type or local_tfv.business_type

        local_tfv.use_case_categories = remote.use_case_categories or []
        local_tfv.use_case_summary = remote.use_case_summary
        local_tfv.production_message_sample = remote.production_message_sample
        local_tfv.additional_information = remote.additional_information or local_tfv.additional_information
        local_tfv.message_volume = int(
            str(remote.message_volume or "0").replace(",", "")
        )
        local_tfv.opt_in_confirmation_message = (
            getattr(
                remote,
                "opt_in_confirmation_message",
                ""
            )
            or local_tfv.opt_in_confirmation_message
        )

        local_tfv.opt_in_type = remote.opt_in_type
        local_tfv.opt_in_image_urls = remote.opt_in_image_urls or local_tfv.opt_in_image_urls
        local_tfv.opt_in_keywords = remote.opt_in_keywords or local_tfv.opt_in_keywords

        local_tfv.help_message_sample = remote.help_message_sample or local_tfv.help_message_sample
        local_tfv.privacy_policy_url = remote.privacy_policy_url or local_tfv.privacy_policy_url
        local_tfv.age_gated_content = remote.age_gated_content

        local_tfv.verification_status = self.map_tfv_status(remote)
        local_tfv.approved_at=(
            remote.date_updated
            if status == "TWILIO_APPROVED"
            else None
        )
        local_tfv.rejected_at=(
            remote.date_updated
            if status == "TWILIO_REJECTED"
            else None
        )

        local_tfv.rejection_reason=remote.rejection_reason or ""
        local_tfv.rejection_reasons=(
            "\n".join(remote.rejection_reasons)
            if remote.rejection_reasons
            else remote.rejection_reason or ""
        )
        local_tfv.rejection_code=remote.error_code or ""
        local_tfv.last_synced_at = timezone.now()
        local_tfv.submitted_at = remote.date_created
        local_tfv.response_payload = convert_dict
        local_tfv.is_verified = status == "TWILIO_APPROVED"
        local_tfv.save()

        self.update_phone_number_status(phone_number, remote)
        return convert_dict

    def map_tfv_status(self, remote) -> str:
        status = (remote.status or "").upper()
        status_map = {
            "SUBMITTED": VerificationStatus.SUBMITTED,
            "PENDING_REVIEW": VerificationStatus.IN_REVIEW,
            "IN_REVIEW": VerificationStatus.IN_REVIEW,
            "IN_PROGRESS": VerificationStatus.PENDING,
            "TWILIO_APPROVED": VerificationStatus.TWILIO_APPROVED,
            "CANCELED": VerificationStatus.CANCELED,
        }
        if status == "TWILIO_REJECTED":
            return VerificationStatus.REJECTED if getattr(remote, "edit_allowed", False) else VerificationStatus.REJECTED_PERMANENT
        return status_map.get(status, VerificationStatus.DRAFT)

    def create_tfv_model(self, phone_number, remote):
        try:
            convert_dict = TFV_to_dict(remote)
            status = (remote.status or "").upper()
            tfv = TollFreeVerification.objects.create(
                # Relations
                free_trail_phone_number=phone_number,
                organization=getattr(phone_number, "organization", None),
                user=getattr(phone_number, "user", None),

                # Twilio
                customer_profile_sid=remote.customer_profile_sid,
                tollfree_phone_number_sid=remote.tollfree_phone_number_sid,
                verification_sid=remote.sid,
                external_reference_id=remote.external_reference_id,

                # Business Information
                business_name=remote.business_name,
                doing_business_as=remote.doing_business_as or "",
                business_website=remote.business_website,
                notification_email=remote.notification_email,
                business_registration_number=remote.business_registration_number or "",
                business_registration_authority=remote.business_registration_authority or "",
                business_registration_country=remote.business_registration_country or "",
                business_registration_phone_number=remote.business_contact_phone or "",
                business_type=remote.business_type or "",

                # Use Case
                use_case_categories=remote.use_case_categories or [],
                use_case_summary=remote.use_case_summary,
                production_message_sample=remote.production_message_sample,
                message_volume=int(str(remote.message_volume or "0").replace(",", "")),
                additional_information=remote.additional_information or "",

                # Opt In
                opt_in_type=remote.opt_in_type,
                opt_in_image_urls=remote.opt_in_image_urls or [],
                opt_in_confirmation_message="",  # Twilio TFV API does not return this field
                opt_in_keywords=remote.opt_in_keywords or [],

                # Compliance
                help_message_sample=remote.help_message_sample or "",
                privacy_policy_url=remote.privacy_policy_url or "",
                terms_and_conditions_url="",  # Not returned by Twilio TFV fetch
                age_gated_content=remote.age_gated_content,

                # Status
                verification_status=self.map_tfv_status(remote),
                is_verified=status == "TWILIO_APPROVED",

                submitted_at=remote.date_created,
                approved_at=(
                    remote.date_updated
                    if status == "TWILIO_APPROVED"
                    else None
                ),
                rejected_at=(
                    remote.date_updated
                    if status == "TWILIO_REJECTED"
                    else None
                ),

                rejection_reason=remote.rejection_reason or "",
                rejection_reasons=(
                    "\n".join(remote.rejection_reasons)
                    if remote.rejection_reasons
                    else remote.rejection_reason or ""
                ),
                rejection_code=remote.error_code or "",

                # Raw API
                request_payload={},
                response_payload=convert_dict,
                last_synced_at=timezone.now(),
            )
            return remote, tfv
        except Exception as e:
            logger.exception(e)
            raise

    def get_latest_ftv(self, phone_number, client):
        data = []
        approved, reviewed, latest, rejected = None, None, None, None
        tfvs = client.messaging.v1.tollfree_verifications.list(
            tollfree_phone_number_sid=phone_number.provider_phone_sid
        )
        if not tfvs:
            return None, []
        latest = max(
            tfvs,
            key=lambda x: x.date_created
        )
        for item in tfvs:
            if item.status == "TWILIO_APPROVED":
                approved = item
                break
            elif item.status in ["PENDING_REVIEW", "IN_REVIEW",]:
                reviewed = item
            elif item.status == "TWILIO_REJECTED":
                rejected = item
            else:
                data.append(TFV_to_dict(item))
        return (approved or reviewed or latest), data
        # return (approved or reviewed or rejected or latest), data

    def sync_tfv_verification(self, phone_number) -> FreeTrailPhoneNumber:
        client = self.get_object_client(phone_number)
        local_tfv = getattr(phone_number, "tfv_verification", None)
        
        if local_tfv and local_tfv.verification_sid:
            try:
                remote = client.messaging.v1.tollfree_verifications(
                    local_tfv.verification_sid
                ).fetch()
                if remote.status == "TWILIO_APPROVED":
                    return self.update_tfv_model(
                        phone_number,
                        local_tfv,
                        remote,
                    )

                twilio_tfv, data = self.get_latest_ftv(
                    phone_number,
                    client,
                )
                if not twilio_tfv:
                    return None
                else:
                    return self.update_tfv_model(
                        phone_number,
                        local_tfv,
                        twilio_tfv,
                    )
                # convert_dict = self.update_tfv_model(phone_number, local_tfv, remote)
                # return convert_dict
            except Exception as e:
                # raise Exception("TFV Object fetch failed.")
                logger.exception(e)
                raise
        else:
            twilio_tfv, data = self.get_latest_ftv(phone_number, client)
            # if local_tfv: local_tfv.delete()
            if not twilio_tfv: return None
            else:
                remote_tfv, local_tfv = self.create_tfv_model(phone_number, twilio_tfv)
                # tfv_verification = twilio_tfv
                
                self.update_phone_number_status(phone_number, remote_tfv)
                if remote_tfv.status in ["TWILIO_APPROVED", "PENDING_REVIEW", "TWILIO_REJECTED", "IN_REVIEW"]:
                    return TFV_to_dict(remote_tfv)
                else:
                    return data

    def submit_tfv_verification(self, phone_number, payload, client):
        try:
            tollfree_verification = (
                client.messaging.v1.tollfree_verifications.create(
                    **payload
                )
            )
            self.create_tfv_model(phone_number, tollfree_verification)
            return tollfree_verification
        except TwilioRestException as exc:
            raise Exception(
                f"Twilio TFV Submit Failed: {exc.msg}"
            )
    # ---------------------------------------------------------------------


