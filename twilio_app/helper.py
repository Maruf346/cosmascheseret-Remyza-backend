from datetime import datetime

def purchase_to_dict(phone):
    return {
        "sid": phone.sid,
        "account_sid": phone.account_sid,
        "phone_number": phone.phone_number,
        "friendly_name": phone.friendly_name,
        "status": phone.status,
        "type": phone.type,
        "origin": phone.origin,
        "capabilities": phone.capabilities,
        "sms_url": phone.sms_url,
        "voice_url": phone.voice_url,
        "sms_method": phone.sms_method,
        "voice_method": phone.voice_method,
        "status_callback": phone.status_callback,
        "status_callback_method": phone.status_callback_method,
        "voice_fallback_url": phone.voice_fallback_url,
        "voice_fallback_method": phone.voice_fallback_method,
        "sms_fallback_url": phone.sms_fallback_url,
        "sms_fallback_method": phone.sms_fallback_method,
        "address_sid": phone.address_sid,
        "bundle_sid": phone.bundle_sid,
        "identity_sid": phone.identity_sid,
        "trunk_sid": phone.trunk_sid,
        "voice_application_sid": phone.voice_application_sid,
        "sms_application_sid": phone.sms_application_sid,
        "voice_receive_mode": phone.voice_receive_mode,
        "voice_caller_id_lookup": phone.voice_caller_id_lookup,
        "emergency_status": phone.emergency_status,
        "emergency_address_sid": phone.emergency_address_sid,
        "emergency_address_status": phone.emergency_address_status,
        "api_version": phone.api_version,
        "address_requirements": phone.address_requirements,
        "beta": phone.beta,
        "uri": phone.uri,
        "date_created": phone.date_created,
        "date_updated": phone.date_updated,
    }

def TFV_to_dict(record):
    return {
        "sid": record.sid,
        "account_sid": record.account_sid,
        "customer_profile_sid": record.customer_profile_sid,
        "regulated_item_sid": record.regulated_item_sid,
        "trust_product_sid": record.trust_product_sid,
        "business_name": record.business_name,
        "status": record.status,
        "date_created": (
            record.date_created.isoformat()
            if record.date_created
            else None
        ),

        "date_updated": (
            record.date_updated.isoformat()
            if record.date_updated
            else None
        ),
        # "date_created": record.date_created,
        # "date_updated": record.date_updated,
        "business_street_address": record.business_street_address,
        "business_street_address2": record.business_street_address2,
        "business_city": record.business_city,
        "business_state_province_region": record.business_state_province_region,
        "business_postal_code": record.business_postal_code,
        "business_country": record.business_country,
        "business_website": record.business_website,
        "business_contact_first_name": record.business_contact_first_name,
        "business_contact_last_name": record.business_contact_last_name,
        "business_contact_email": record.business_contact_email,
        "business_contact_phone": record.business_contact_phone,
        "notification_email": record.notification_email,
        "use_case_categories": record.use_case_categories,
        "use_case_summary": record.use_case_summary,
        "production_message_sample": record.production_message_sample,
        "opt_in_image_urls": record.opt_in_image_urls,
        "opt_in_type": record.opt_in_type,
        "message_volume": record.message_volume,
        "additional_information": record.additional_information,
        "tollfree_phone_number_sid": record.tollfree_phone_number_sid,
        "rejection_reason": record.rejection_reason,
        "error_code": record.error_code,
        "edit_expiration": record.edit_expiration,
        "edit_allowed": record.edit_allowed,
        "rejection_reasons": record.rejection_reasons,
        "resource_links": record.resource_links,
        "url": record.url,
        "external_reference_id": record.external_reference_id,

        # // New response fields for the 2026 update
        "business_registration_number": record.business_registration_number,
        "business_registration_authority": record.business_registration_authority,
        "business_registration_country": record.business_registration_country,
        "doing_business_as": record.doing_business_as,
        "business_type": record.business_type,
        # "opt_in_confirmation_sample": record.opt_in_confirmation_sample,
        "help_message_sample": record.help_message_sample,
        "privacy_policy_url": record.privacy_policy_url,
        # "terms_and_condition_url": record.terms_and_condition_url,
        "age_gated_content": record.age_gated_content,
        "opt_in_keywords": record.opt_in_keywords,
        
        # // New response fields for CV Token update
        "vetting_id": record.vetting_id,       
        "vetting_provider": record.vetting_provider,
        "vetting_id_expiration": record.vetting_id_expiration
    }

def MessageService_to_Dict(service):
    return {
        "sid": service.sid,
        "account_sid": service.account_sid,
        "friendly_name": service.friendly_name,
        "status": getattr(service, "status", "ACTIVE"),
        "inbound_request_url": getattr(service, "inbound_request_url", None),
        "fallback_url": getattr(service, "fallback_url", None),
        "status_callback": getattr(service, "status_callback", None),
        "usecase": getattr(service, "usecase", None),
        "links": getattr(service, "links", {}),
        "date_created": (service.date_created.isoformat() if service.date_created else None),
        "date_updated": (service.date_updated.isoformat() if service.date_updated else None),
    }

def TrustHubPolicy_to_Dict(policy):
    return {
        "sid": policy.sid,
        "friendly_name": getattr(policy, "friendly_name", ""),
        "type": getattr(policy, "type", ""),
        "status": getattr(policy, "status", ""),
        "url": getattr(policy, "url", ""),
    }

def CustomerProfile_to_Dict(profile):
    return {
        "sid": profile.sid,
        "account_sid": profile.account_sid,
        "policy_sid": profile.policy_sid,
        "friendly_name": profile.friendly_name,
        "status": profile.status, # twilio-approved or 
        "email": getattr(profile, "email", None),
        "url": getattr(profile, "url", None),
        "links": getattr(profile, "links", {}),
        "date_created": (
            profile.date_created.isoformat()
            if getattr(profile, "date_created", None)
            else None
        ),
        "date_updated": (
            profile.date_updated.isoformat()
            if getattr(profile, "date_updated", None)
            else None
        ),
    }

def EndUserSerializer(end_user):
    return {
        "sid": end_user.sid,
        "account_sid": end_user.account_sid,
        "friendly_name": end_user.friendly_name,
        "type": end_user.type,
        "attributes": end_user.attributes,
        "date_created": end_user.date_created.isoformat() if getattr(end_user, "date_created", None) else None,
        "date_updated": end_user.date_updated.isoformat() if getattr(end_user, "date_updated", None) else None
    }

def TwilioAddressSerializer(addresses):
    return {
        "sid": addresses.sid,
        "account_sid": addresses.account_sid,
        "customer_name": addresses.customer_name,
        "friendly_name": addresses.friendly_name,
        "street": addresses.street,
        "street_secondary": addresses.street_secondary,
        "city": addresses.city,
        "region": addresses.region,
        "postal_code": addresses.postal_code,
        "iso_country": addresses.iso_country,
        "date_created": addresses.date_created.isoformat() if getattr(addresses, "date_created", None) else None,
        "date_updated": addresses.date_updated.isoformat() if getattr(addresses, "date_updated", None) else None,
        "emergency_enabled": addresses.emergency_enabled,
        "validated": addresses.validated,
        "verified": addresses.verified
    }

def A2PProfileSerializer(profile):
    return {
        "sid": profile.sid,
        "account_sid": profile.account_sid,
        "policy_sid": profile.policy_sid,
        "friendly_name": profile.friendly_name,
        "status": profile.status,
        "valid_until": profile.valid_until,
        "email": profile.email,
        "status_callback": profile.status_callback,
        "date_created": (
            profile.date_created.isoformat()
            if isinstance(profile.date_created, datetime)
            else profile.date_created
        ),
        "date_updated": (
            profile.date_updated.isoformat()
            if isinstance(profile.date_updated, datetime)
            else profile.date_updated
        ),
        "url": profile.url,
        "links": profile.links,
        "errors": profile.errors,
    }

def A2PEvaluationSerializer(evaluation):
    return {
        "sid": evaluation.sid,
        "account_sid": evaluation.account_sid,
        "policy_sid": evaluation.policy_sid,
        "customer_profile_sid": evaluation.customer_profile_sid,
        "status": evaluation.status,
        "results": evaluation.results,
        "date_created": (
            evaluation.date_created.isoformat()
            if isinstance(evaluation.date_created, datetime)
            else evaluation.date_created
        ),
        "url": evaluation.url,
    }

def BrandSerializer(brand):
    return {
        "brand_sid": brand.sid,
        "account_sid": brand.account_sid,
        "customer_profile_bundle_sid": brand.customer_profile_bundle_sid,
        "a2p_profile_bundle_sid": brand.a2p_profile_bundle_sid,
        "brand_type": brand.brand_type,
        "status": brand.status,
        "tcr_id": brand.tcr_id,
        "failure_reason": brand.failure_reason,
        "brand_score": brand.brand_score,
        "brand_feedback": list(brand.brand_feedback or []),
        "identity_status": brand.identity_status,
        "russell_3000": brand.russell_3000,
        "government_entity": brand.government_entity,
        "tax_exempt_status": brand.tax_exempt_status,
        "skip_automatic_sec_vet": brand.skip_automatic_sec_vet,
        "mock": brand.mock,
        "errors": list(brand.errors or []),
        "links": dict(brand.links or {}),
        "url": brand.url,
        "date_created": (
            brand.date_created.isoformat()
            if isinstance(brand.date_created, datetime)
            else brand.date_created
        ),
        "date_updated": (
            brand.date_updated.isoformat()
            if isinstance(brand.date_updated, datetime)
            else brand.date_updated
        ),
    }


