import uuid

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class SentDMClientError(Exception):
    def __init__(self, message, *, status_code=None, response_data=None, request_id=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data
        self.request_id = request_id


class SentDMClient:
    def __init__(self, api_key=None, base_url=None, timeout=30):
        self.api_key = api_key or getattr(settings, "SENTDM_API_KEY", "")
        self.base_url = (base_url or getattr(settings, "SENTDM_API_BASE", "")).rstrip("/")
        self.timeout = timeout

        if not self.api_key:
            raise ImproperlyConfigured("SENTDM_API_KEY is not configured.")
        if not self.base_url:
            raise ImproperlyConfigured("SENTDM_API_BASE is not configured.")

    def _headers(self, profile_id=None, idempotency_key=None):
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        if profile_id:
            headers["x-profile-id"] = profile_id
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _request(self, method, path, *, profile_id=None, idempotency_key=None, json=None):
        try:
            response = requests.request(
                method=method,
                url=f"{self.base_url}{path}",
                headers=self._headers(profile_id=profile_id, idempotency_key=idempotency_key),
                json=json,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise SentDMClientError(str(exc)) from exc

        request_id = response.headers.get("X-Request-Id") or response.headers.get("x-request-id")

        if response.status_code == 204:
            return {
                "success": True,
                "data": None,
                "meta": {"request_id": request_id},
                "_headers": dict(response.headers),
            }

        try:
            response_data = response.json()
        except ValueError:
            response_data = {"raw": response.text}

        if response.status_code >= 400:
            message = response_data.get("message") or response_data.get("error") or response.text
            raise SentDMClientError(
                message,
                status_code=response.status_code,
                response_data=response_data,
                request_id=request_id,
            )

        if isinstance(response_data, dict):
            response_data["_headers"] = dict(response.headers)
        return response_data

    def with_sandbox(self, payload):
        if getattr(settings, "SENTDM_SANDBOX_MODE", True):
            return {**payload, "sandbox": True}
        return payload

    def get_account(self):
        return self._request("GET", "/me")

    def list_profiles(self):
        return self._request("GET", "/profiles")

    def create_profile(self, payload, *, idempotency_key=None):
        return self._request(
            "POST",
            "/profiles",
            json=self.with_sandbox(payload),
            idempotency_key=idempotency_key or f"chesera-profile-{uuid.uuid4()}",
        )

    def get_profile(self, profile_id):
        return self._request("GET", f"/profiles/{profile_id}")

    def complete_profile(self, profile_id, webhook_url, *, idempotency_key=None):
        return self._request(
            "POST",
            f"/profiles/{profile_id}/complete",
            json=self.with_sandbox({"webHookUrl": webhook_url}),
            idempotency_key=idempotency_key or f"chesera-complete-{profile_id}",
        )

    def create_campaign(self, profile_id, payload, *, idempotency_key=None):
        return self._request(
            "POST",
            f"/profiles/{profile_id}/campaigns",
            json=self.with_sandbox(payload),
            idempotency_key=idempotency_key or f"chesera-campaign-{profile_id}-{uuid.uuid4()}",
        )

    def send_message(self, *, to, text, profile_id=None, channel=None, idempotency_key=None):
        payload = {"to": [to], "text": text}
        if channel and channel != "auto":
            payload["channel"] = [channel]

        return self._request(
            "POST",
            "/messages",
            profile_id=profile_id,
            json=self.with_sandbox(payload),
            idempotency_key=idempotency_key or f"chesera-message-{uuid.uuid4()}",
        )

