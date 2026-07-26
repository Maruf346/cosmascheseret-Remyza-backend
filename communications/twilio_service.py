import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from django.conf import settings

class TwilioService:
    def __init__(self):
        # Master account credentials
        self.master_account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', os.getenv('TWILIO_ACCOUNT_SID'))
        self.master_auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', os.getenv('TWILIO_AUTH_TOKEN'))
        if self.master_account_sid and self.master_auth_token:
            self.client = Client(self.master_account_sid, self.master_auth_token)
        else:
            self.client = None

    def create_sub_account(self, friendly_name: str) -> dict:
        """Creates a Twilio Subaccount for a new paid user/organization."""
        if not self.client:
            return {"success": False, "error": "Twilio client not initialized"}
        try:
            account = self.client.api.accounts.create(friendly_name=friendly_name)
            return {
                "success": True,
                "sub_account_sid": account.sid,
                "auth_token": account.auth_token
            }
        except TwilioRestException as e:
            return {"success": False, "error": str(e)}

    def search_available_numbers(self, country_code: str = 'US', area_code: str = None, toll_free: bool = False, limit: int = 5) -> dict:
        """Searches for available Twilio phone numbers (Local or Toll-Free)."""
        if not self.client:
            return {"success": False, "error": "Twilio client not initialized"}
        try:
            if toll_free:
                numbers = self.client.available_phone_numbers(country_code).toll_free.list(limit=limit)
            else:
                numbers = self.client.available_phone_numbers(country_code).local.list(
                    area_code=area_code, limit=limit
                )
            
            return {
                "success": True,
                "numbers": [
                    {
                        "phone_number": n.phone_number, 
                        "locality": getattr(n, 'locality', ''), 
                        "rate_center": getattr(n, 'rate_center', '')
                    }
                    for n in numbers
                ]
            }
        except TwilioRestException as e:
            return {"success": False, "error": str(e)}

    def purchase_number(self, sub_account_sid: str, phone_number: str) -> dict:
        """Purchases a specific phone number under a specific Sub-account."""
        if not self.client:
            return {"success": False, "error": "Twilio client not initialized"}
        try:
            # The master client can create an incoming phone number on the subaccount's resource URL.
            sub_client = self.client.api.accounts(sub_account_sid)
            purchased_number = sub_client.incoming_phone_numbers.create(phone_number=phone_number)
            
            return {
                "success": True,
                "sid": purchased_number.sid,
                "phone_number": purchased_number.phone_number
            }
        except TwilioRestException as e:
            return {"success": False, "error": str(e)}

    def submit_a2p_tfv_verification(self, sub_account_sid: str, business_profile: dict) -> dict:
        """
        Submits A2P 10DLC or Toll-Free Verification for compliance.
        This provides the structural scaffolding to build out the full TrustHub integration.
        """
        if not self.client:
            return {"success": False, "error": "Twilio client not initialized"}
        try:
            # Note: A real A2P registration flow involves multiple TrustHub calls:
            # 1. Create a Customer Profile
            # 2. Create an A2P Brand
            # 3. Create a Messaging Service
            # 4. Create an A2P Campaign use case
            
            # Scaffold return payload
            return {
                "success": True,
                "message": "A2P/TFV compliance profile submitted successfully. (Scaffolded)",
                "verification_status": "PENDING"
            }
        except TwilioRestException as e:
            return {"success": False, "error": str(e)}
