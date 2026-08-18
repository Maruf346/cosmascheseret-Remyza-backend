from .services import TwilioLocalVerificationService
from twilio.rest import Client
from twilio_app.helper import CustomerProfile_to_Dict, TrustHubPolicy_to_Dict, A2PEvaluationSerializer, A2PProfileSerializer, BrandSerializer, MessageService_to_Dict
from twilio.base.exceptions import TwilioRestException
import os

class LocalNumberVerificationHelper:
    def __init__(self, user, phone_number, organization):
        self.user = user
        self.phone_number = phone_number
        self.organization = organization
        self.local_verification = self.phone_number.local_verification
        self.client = self.master_client()

    # Client
    def master_client(self) -> Client:
        ACCOUNT_SID = os.getenv("ACCOUNT_SID")
        AUTH_TOKEN = os.getenv("AUTH_TOKEN")
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        return client

    def get_messaging_service(self):
        local_verification = self.local_verification
        if local_verification.messaging_service:
            return local_verification.messaging_service
        else:
            return self.verification_service.assign_phone_number()

    def get_a2p_brand(self, data):
        local_verification = self.get_local_verification()
        if local_verification.a2p_brand:
            a2p_brand = local_verification.a2p_brand
        else:
            a2p_brand = self.verification_service.register_brand(data)

    def return_data(self):
        local_verification = self.get_local_verification()
        return [
            {
                "title": "Messaging Service",
                "completed": local_verification.messaging_service is not None,
            },

            {
                "title": "A2P Brand",
                "completed": local_verification.a2p_brand is not None,
            },

            {
                "title": "A2P Campaign",
                "completed": local_verification.a2p_campaign is not None,
            },

        ]

    def verification_step_one(self, data):
        local_verification = self.get_local_verification()
        self.verification_service = TwilioLocalVerificationService(
            user=self.user,
            phone_number=self.phone_number,
            organization=self.organization
        )

        messaging_service = self.get_messaging_service()
        a2p_brand = self.get_a2p_brand(data)

        local_verification.refresh_from_db()
        return self.return_data(), a2p_brand




    def get_policies(self):
        try:
            client = self.client
            policies = client.trusthub.v1.policies.list()
            data = [TrustHubPolicy_to_Dict(policy) for policy in policies]
            return data
        except TwilioRestException:
            raise

    def get_primary_customer_profile(self, client=None):
        try:
            if client:
                return client.trusthub.v1.customer_profiles.list()[0]
            else:
                return self.client.trusthub.v1.customer_profiles.list()[0]
        except TwilioRestException:
            raise

    def get_primary_customer_profile_policy_sid(self, client):
        print("[GET START] Primary Customer Profile")
        primary_customer_profile = self.get_primary_customer_profile(client)
        print("[GET] Primary Customer Profile:", primary_customer_profile.sid)
        print("[GET] Primary Customer Profile Status:", primary_customer_profile.status)
        print("[GET] Primary Customer Profile Policy:", primary_customer_profile.policy_sid)
        print("[GET END] Primary Customer Profile")
        policy_sid = primary_customer_profile.policy_sid
        if not policy_sid:
            raise Exception("Primary Customer Profile Policy SID not found.")
        return policy_sid

    def verification_customer_profile(self, data):
        provider = self.organization.provider_account
        client = Client(provider.account_sid, provider.auth_token)
        local_verification = self.local_verification

        # ============================================================
        # 1. GET PRIMARY CUSTOMER PROFILE
        # ============================================================
        # primary_customer_profile_policy_sid = self.get_primary_customer_profile_policy_sid(client)
        secondary_profile_policy_sid = os.getenv("SECONDARY_CUSTOMER_PROFILE_POLICY_SID")
        print("[DEBUG] Secondary Policy SID:", secondary_profile_policy_sid)
        print("===============================================================================")

        # ============================================================
        # 2. CREATE / GET SECONDARY CUSTOMER PROFILE
        # ============================================================
        print("[CREATE START] Secondary Customer Profile")
        if local_verification.customer_profile_sid:
            print("[GET] Secondary Customer Profile:", local_verification.customer_profile_sid)
            customer_profile = client.trusthub.v1.customer_profiles(
                sid=local_verification.customer_profile_sid
            ).fetch()
            print("[GET] Secondary Customer Profile Status:", customer_profile.status)
            if customer_profile.status == "twilio-approved":
                return CustomerProfile_to_Dict(customer_profile)
        else:
            customer_profile_all = client.trusthub.v1.customer_profiles.list()
            print("[GET] All Customer Profile:", customer_profile_all)

            customer_profile = client.trusthub.v1.customer_profiles.create(
                friendly_name=self.organization.name,
                email=self.organization.email,
                policy_sid=secondary_profile_policy_sid,
            )

            local_verification.customer_profile_sid = customer_profile.sid
            local_verification.save()
            print("[CREATE] Secondary Customer Profile:", customer_profile.sid)

        print("[CREATE END] Secondary Customer Profile")

        print("===============================================================================")

        # ============================================================
        # 3. CREATE / GET BUSINESS END USER
        # ============================================================
        print("[CREATE START] Business End User")
        if local_verification.end_user_sid:
            end_user = client.trusthub.v1.end_users(
                sid=local_verification.end_user_sid
            ).fetch()
            print("[GET] Business End User:", end_user)
        else:
            end_user_all = client.trusthub.v1.end_users.list()
            print("[GET] All End User:", end_user_all)

            end_user = client.trusthub.v1.end_users.create(
                type="customer_profile_business_information",
                friendly_name=f"{self.organization.name} - enduser",
                attributes={
                    "business_name": self.organization.name,
                    "business_type": self.organization.business_type.name,
                    "business_industry": self.organization.industry.name,
                    "business_identity": data.get(
                        "business_identity",
                        "direct_customer"
                    ),
                    "business_regions_of_operation": data.get(
                        "business_regions_of_operation",
                        "USA_AND_CANADA"
                    ),
                    "business_registration_identifier": self.organization.business_registration_identifier,
                    "business_registration_number": self.organization.business_registration_number,
                    "website_url": self.organization.website,
                    "social_media_profile_urls": data.get(
                        "social_media_profile_urls",
                        ""
                    ),
                }
            )

            local_verification.end_user_sid = end_user.sid
            local_verification.save()
            print("[CREATE] Business End User:", end_user.sid)

        print("[CREATE END] Business End User")

        print("===============================================================================")

        # ============================================================
        # 4. CREATE / GET AUTHORIZED REPRESENTATIVE 1
        # ============================================================
        print("[CREATE START] Authorized Representative 1")
        if local_verification.authorized_representative_1_sid:
            authorized_representative_1 = client.trusthub.v1.end_users(
                sid=local_verification.authorized_representative_1_sid
            ).fetch()
            print("[GET] Authorized Representative 1:", authorized_representative_1)
        else:
            authorized_representative_1_all = client.trusthub.v1.end_users.list()
            print("[GET] All Authorized Representative 1:", authorized_representative_1_all)

            authorized_representative_1 = client.trusthub.v1.end_users.create(
                type="authorized_representative_1",
                friendly_name=f"{self.organization.name} - authorized representative 1",
                attributes={
                    "first_name": data.get("representative_1_first_name"),
                    "last_name": data.get("representative_1_last_name"),
                    "email": data.get("representative_1_email"),
                    "phone_number": data.get("representative_1_phone_number"),
                    "business_title": data.get("representative_1_business_title"),
                    "job_position": data.get("representative_1_job_position"),
                }
            )

            local_verification.authorized_representative_1_sid = authorized_representative_1.sid
            local_verification.save()
            print("[CREATE] Authorized Representative 1:", authorized_representative_1)

        print("[CREATE END] Authorized Representative 1")

        print("===============================================================================")

        # ============================================================
        # 5. CREATE / GET AUTHORIZED REPRESENTATIVE 2
        # ============================================================
        # print("[CREATE START] Authorized Representative 2")
        # if local_verification.authorized_representative_2_sid:
        #     print("[GET] Authorized Representative 2:", local_verification.authorized_representative_2_sid)
        #     authorized_representative_2 = client.trusthub.v1.end_users(
        #         sid=local_verification.authorized_representative_2_sid
        #     ).fetch()
        # else:
        #     authorized_representative_2 = client.trusthub.v1.end_users.create(
        #         type="authorized_representative_2",
        #         friendly_name=f"{self.organization.name} - authorized representative 2",
        #         attributes={
        #             "first_name": data.get("representative_2_first_name"),
        #             "last_name": data.get("representative_2_last_name"),
        #             "email": data.get("representative_2_email"),
        #             "phone_number": data.get("representative_2_phone_number"),
        #             "business_title": data.get("representative_2_business_title"),
        #             "job_position": data.get("representative_2_job_position"),
        #         }
        #     )

        #     local_verification.authorized_representative_2_sid = authorized_representative_2.sid
        #     local_verification.save()

        #     print("[CREATE] Authorized Representative 2:", authorized_representative_2.sid)

        # print("[CREATE END] Authorized Representative 2")

        # print("===============================================================================")

        # ============================================================
        # 6. CREATE / GET BUSINESS ADDRESS
        # ============================================================
        print("[CREATE START] Business Address")
        if local_verification.address_sid:
            address = client.addresses(
                sid=local_verification.address_sid
            ).fetch()
            print("[GET] Business Address:", address)
        else:
            addresses_all = client.addresses.list()
            print("[GET] All Address:", addresses_all)
            
            address = client.addresses.create(
                customer_name=self.organization.name,
                street=data.get("street"),
                street_secondary=data.get("street_secondary", ""),
                city=data.get("city"),
                region=data.get("state"),
                postal_code=data.get("postal_code"),
                iso_country=data.get("country", "US"),
            )

            local_verification.address_sid = address.sid
            local_verification.save()
            print("[CREATE] Business Address:", address)

        print("[CREATE END] Business Address")

        print("===============================================================================")


        # ============================================================
        # 7. CREATE / GET SUPPORTING DOCUMENT
        # ============================================================
        print("[CREATE START] Supporting Document")
        if local_verification.supporting_document_sid:
            supporting_document = client.trusthub.v1.supporting_documents(
                sid=local_verification.supporting_document_sid
            ).fetch()
            print("[GET] Supporting Document:", supporting_document)
        else:
            supporting_document_all = client.trusthub.v1.supporting_documents.list()
            print("[GET] All Supporting Document:", supporting_document_all)

            supporting_document = client.trusthub.v1.supporting_documents.create(
                type="customer_profile_address",
                friendly_name=f"Business Address [{customer_profile.sid}]",
                attributes={
                    "address_sids": address.sid
                },
            )

            local_verification.supporting_document_sid = supporting_document.sid
            local_verification.save()
            print("[CREATE] Supporting Document:", supporting_document)

        print("[CREATE END] Supporting Document")

        print("===============================================================================")


        # ============================================================
        # 8. ASSIGN BUSINESS END USER
        # ============================================================
        print("[CREATE START] End User Assignment")
        if local_verification.end_user_assign_to_customer_profiles_sid:
            end_user_assignment = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_entity_assignments(
                sid=local_verification.end_user_assign_to_customer_profiles_sid
            ).fetch()
            print("[GET] End User Assignment:", end_user_assignment)
        else:
            end_user_assign_to_customer_profiles_all = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_entity_assignments.list()
            print("[GET] All End User Assign:", end_user_assign_to_customer_profiles_all)
            
            end_user_assignment = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_entity_assignments.create(
                object_sid=end_user.sid
            )

            local_verification.end_user_assign_to_customer_profiles_sid = end_user_assignment.sid
            local_verification.save()
            print("[CREATE] End User Assignment:", end_user_assignment)

        print("[CREATE END] End User Assignment")

        print("===============================================================================")


        # ============================================================
        # 9. ASSIGN AUTHORIZED REPRESENTATIVE 1
        # ============================================================
        print("[CREATE START] Authorized Representative 1 Assignment")
        if local_verification.authorized_representative_1_assign_to_customer_profiles_sid:
            authorized_representative_1_assignment = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_entity_assignments(
                sid=local_verification.authorized_representative_1_assign_to_customer_profiles_sid
            ).fetch()
            print("[GET] Authorized Representative 1 Assignment:", authorized_representative_1_assignment)
        else:
            authorized_representative_1_assignment_all = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_entity_assignments.list()
            print("[GET] All Authorized Representative 1 Assign:", authorized_representative_1_assignment_all)

            authorized_representative_1_assignment = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_entity_assignments.create(
                object_sid=authorized_representative_1.sid
            )

            local_verification.authorized_representative_1_assign_to_customer_profiles_sid = authorized_representative_1_assignment.sid
            local_verification.save()
            print("[CREATE] Authorized Representative 1 Assignment:", authorized_representative_1_assignment)

        print("[CREATE END] Authorized Representative 1 Assignment")

        print("===============================================================================")


        # ============================================================
        # 10. ASSIGN AUTHORIZED REPRESENTATIVE 2
        # ============================================================
        # print("[CREATE START] Authorized Representative 2 Assignment")
        # if local_verification.authorized_representative_2_assign_to_customer_profiles_sid:
        #     authorized_representative_2_assignment = client.trusthub.v1.customer_profiles(
        #         sid=customer_profile.sid
        #     ).customer_profiles_entity_assignments(
        #         sid=local_verification.authorized_representative_2_assign_to_customer_profiles_sid
        #     ).fetch()
        #     print("[GET] Authorized Representative 2 Assignment:", authorized_representative_2_assignment)
        # else:
        #     authorized_representative_2_assignment_all = client.trusthub.v1.customer_profiles(
        #         sid=customer_profile.sid
        #     ).customer_profiles_entity_assignments.list()
        #     print("[GET] All Authorized Representative 2 Assign:", authorized_representative_2_assignment_all)

        #     authorized_representative_2_assignment = client.trusthub.v1.customer_profiles(
        #         sid=customer_profile.sid
        #     ).customer_profiles_entity_assignments.create(
        #         object_sid=authorized_representative_2.sid
        #     )

        #     local_verification.authorized_representative_2_assign_to_customer_profiles_sid = authorized_representative_2_assignment.sid
        #     local_verification.save()
        #     print("[CREATE] Authorized Representative 2 Assignment:", authorized_representative_2_assignment)

        # print("[CREATE END] Authorized Representative 2 Assignment")

        # print("===============================================================================")


        # ============================================================
        # 12. ASSIGN SUPPORTING DOCUMENT
        # ============================================================
        print("[CREATE START] Supporting Document Assignment")
        if local_verification.supporting_document_assign_to_customer_profile_sid:
            supporting_document_assignment = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_entity_assignments(
                sid=local_verification.supporting_document_assign_to_customer_profile_sid
            ).fetch()
            print("[GET] Supporting Document Assignment:", supporting_document_assignment)
        else:
            supporting_document_assignment_all = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_entity_assignments.list()
            print("[GET] All Supporting Document Assign:", supporting_document_assignment_all)

            supporting_document_assignment = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_entity_assignments.create(
                object_sid=supporting_document.sid
            )

            local_verification.supporting_document_assign_to_customer_profile_sid = supporting_document_assignment.sid
            local_verification.save()
            print("[CREATE] Supporting Document Assignment:", supporting_document_assignment)

        print("[CREATE END] Supporting Document Assignment")

        print("===============================================================================")


        # ============================================================
        # 11. ASSIGN PRIMARY CUSTOMER PROFILE
        # ============================================================
        print("[CREATE START] Primary Customer Profile Assignment")
        if local_verification.primary_customer_profile_assign_to_customer_profile_sid:
            primary_assignment = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_entity_assignments(
                sid=local_verification.primary_customer_profile_assign_to_customer_profile_sid
            ).fetch()
            print("[GET] Primary Customer Profile Assignment:", primary_assignment)
        else:
            primary_assignment_all = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_entity_assignments.list()
            print("[GET] All Primary Customer Profile Assign:", primary_assignment_all)

            primary_assignment = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_entity_assignments.create(
                object_sid=self.get_primary_customer_profile().sid
            )
            local_verification.primary_customer_profile_assign_to_customer_profile_sid = primary_assignment.sid
            local_verification.save()
            print("[CREATE] Primary Customer Profile Assignment:", primary_assignment)

        print("[CREATE END] Primary Customer Profile Assignment")

        print("===============================================================================")


        # ============================================================
        # 13. ASSIGN PHONE NUMBER
        # ============================================================
        print("[CREATE START] Phone Number Assignment")
        try:
            if local_verification.phone_number_assign_to_customer_profile_sid:
                phone_number_assignment = client.trusthub.v1.customer_profiles(
                    sid=customer_profile.sid
                ).customer_profiles_channel_endpoint_assignment(
                    sid=local_verification.phone_number_assign_to_customer_profile_sid
                ).fetch()
                print("[GET] Phone Number Assignment:", phone_number_assignment)
            else:
                phone_number_assignment_all = client.trusthub.v1.customer_profiles(
                    sid=customer_profile.sid
                ).customer_profiles_entity_assignments.list()
                print("[GET] All Phone Number SID Assign:", phone_number_assignment_all)

                phone_number_sid = self.phone_number.provider_phone_sid
                if phone_number_sid:
                    phone_number_assignment = client.trusthub.v1.customer_profiles(
                        sid=customer_profile.sid
                    ).customer_profiles_channel_endpoint_assignment.create(
                        channel_endpoint_sid=phone_number_sid,
                        channel_endpoint_type="phone-number",
                    )

                    local_verification.phone_number_assign_to_customer_profile_sid = phone_number_assignment.sid
                    local_verification.save()
                    print("[CREATE] Phone Number Assignment:", phone_number_assignment)
                else:
                    phone_number_assignment = None
                    print("[SKIP] Phone Number SID not provided")
        except Exception as e:
            print("[SKIP] Phone Number Assign Getting Error: ", str(e))
        print("[CREATE END] Phone Number Assignment")

        print("===============================================================================")


        # ============================================================
        # 14. CREATE / GET PROFILE EVALUATION
        # ============================================================
        print("[CREATE START] Profile Evaluation")
        if local_verification.profile_evaluation_sid:
            profile_evaluation = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_evaluations(
                sid=local_verification.profile_evaluation_sid
            ).fetch()
            print("[GET] Profile Evaluation:", profile_evaluation)
        else:
            profile_evaluation_all = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_evaluations.list()
            print("[GET] All Customer Profile Evaluation Assign:", profile_evaluation_all)

            profile_evaluation = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            ).customer_profiles_evaluations.create(
                policy_sid=customer_profile.policy_sid
            )

            local_verification.profile_evaluation_sid = profile_evaluation.sid
            local_verification.save()
            print("[CREATE] Profile Evaluation:", profile_evaluation)

        print("[CREATE END] Profile Evaluation")

        print("===============================================================================")


        # ============================================================
        # 15. GET EVALUATION RESULT
        # ============================================================
        print("[GET START] Profile Evaluation Result")
        profile_evaluation = client.trusthub.v1.customer_profiles(
            sid=customer_profile.sid
        ).customer_profiles_evaluations(
            sid=profile_evaluation.sid
        ).fetch()
        print("[GET] Profile Evaluation SID:", profile_evaluation.sid)
        print("[GET] Profile Evaluation Status:", profile_evaluation.status)
        print("[GET] Profile Evaluation Results:", profile_evaluation.results)
        try:
            print("[GET] Profile Evaluation Whole Data:", A2PEvaluationSerializer(profile_evaluation))
        except:
            pass
        print("[GET END] Profile Evaluation Result")

        print("===============================================================================")


        # ============================================================
        # 16. SUBMIT SECONDARY CUSTOMER PROFILE
        # ============================================================
        print("[UPDATE START] Secondary Customer Profile")
        if profile_evaluation.status == "compliant":
            customer_profile = client.trusthub.v1.customer_profiles(
                sid=customer_profile.sid
            )
            if customer_profile.status == "draft":
                customer_profile.update(status="pending-review")
            print("[UPDATE] Secondary Customer Profile:", customer_profile.sid)
            print("[UPDATE] Secondary Customer Profile Status:", customer_profile.status)
        else:
            print("[SKIP] Secondary Customer Profile is not compliant")
            print("[SKIP] Evaluation Status:", profile_evaluation.status)
            print("[SKIP] Evaluation Results:", profile_evaluation.results)

        print("[UPDATE END] Secondary Customer Profile")



        print("===========================================================")
        print("END Verification Customer Profile")
        print("===========================================================")
        # return customer_profile
        return CustomerProfile_to_Dict(customer_profile)

    def verification_a2p_profile(self, data):
        provider = self.organization.provider_account
        client = Client(provider.account_sid, provider.auth_token)
        local_verification = self.local_verification

        # ============================================================
        # 2. CREATE / GET TRUSTED BUNDLE PRODUCT
        # ============================================================
        print("[CREATE START] A2P Trusted Bundle")
        if local_verification.a2p_profile_sid:
            trust_product = client.trusthub.v1.trust_products(
                sid=local_verification.a2p_profile_sid
            ).fetch()
            print("[GET] A2P Trusted Bundle:", trust_product)
        else:
            trust_product = client.trusthub.v1.trust_products.create(
                friendly_name=f"{self.organization.name} A2P Trusted Profile",
                email=self.organization.email,
                policy_sid=os.getenv("trust_hub_policy_sid"),
            )

            local_verification.a2p_profile_sid = trust_product.sid
            local_verification.save()
            print("[CREATE] A2P Trusted Bundle:", trust_product)

        print("[CREATE END] A2P Trusted Bundle")

        print("===============================================================================")

        # ============================================================
        # 3. CREATE / GET A2P END USER
        # ============================================================
        print("[CREATE START] A2P End User")
        if local_verification.a2p_end_user_sid:
            a2p_end_user = client.trusthub.v1.end_users(
                sid=local_verification.a2p_end_user_sid
            ).fetch()
            print("[GET] A2P End User:", a2p_end_user)
        else:
            a2p_end_user = client.trusthub.v1.end_users.create(
                type="us_a2p_messaging_profile_information",
                friendly_name=f"{self.organization.name} - Messaging Profile EndUser",
                attributes={
                    "company_type": "private",
                    # "stock_exchange": "NYSE",
                    # "stock_ticker": "ACME",
                }
            )

            local_verification.a2p_end_user_sid = a2p_end_user.sid
            local_verification.save()
            print("[CREATE] A2P End User:", a2p_end_user)

        print("[CREATE END] A2P End User")

        print("===============================================================================")

        # ============================================================
        # 8. ASSIGN BUSINESS END USER
        # ============================================================
        print("[CREATE START] A2P End User Assignment")
        if local_verification.end_user_assign_to_a2p_sid:
            end_user_assign_to_a2p = client.trusthub.v1.trust_products(
                sid=trust_product.sid
            ).trust_products_entity_assignments(
                sid=local_verification.end_user_assign_to_a2p_sid
            ).fetch()
            print("[GET] End User Assignment:", end_user_assign_to_a2p)
        else:
            end_user_assign_to_a2p = client.trusthub.v1.trust_products(
                sid=trust_product.sid
            ).trust_products_entity_assignments.create(
                object_sid=a2p_end_user.sid
            )

            local_verification.end_user_assign_to_a2p_sid = end_user_assign_to_a2p.sid
            local_verification.save()
            print("[CREATE] End User Assignment:", end_user_assign_to_a2p)

        print("[CREATE END] A2P End User Assignment")

        print("===============================================================================")


        # ============================================================
        # 9. ASSIGN SECONDARY CUSTOMER PROFILE
        # ============================================================
        print("[CREATE START] A2P Customer Profile Assign")
        if local_verification.customer_profile_assign_to_a2p_sid:
            customer_profile_assign_to_a2p = client.trusthub.v1.trust_products(
                sid=trust_product.sid
            ).trust_products_entity_assignments(
                sid=local_verification.customer_profile_assign_to_a2p_sid
            ).fetch()
            print("[GET] Customer Profile Assignment:", customer_profile_assign_to_a2p)
        else:
            customer_profile_assign_to_a2p = client.trusthub.v1.trust_products(
                sid=trust_product.sid
            ).trust_products_entity_assignments.create(
                object_sid=local_verification.customer_profile_sid
            )

            local_verification.customer_profile_assign_to_a2p_sid = customer_profile_assign_to_a2p.sid
            local_verification.save()
            print("[CREATE] Customer Profile Assignment:", customer_profile_assign_to_a2p)

        print("[CREATE END] A2P Customer Profile Assign")

        print("===============================================================================")


        # ============================================================
        # 14. CREATE / GET PROFILE EVALUATION
        # ============================================================
        print("[CREATE START] A2P Trusted Product Evaluation")
        if local_verification.a2p_evaluation_sid:
            a2p_evaluation = client.trusthub.v1.trust_products(
                sid=trust_product.sid
            ).trust_products_evaluations(
                sid=local_verification.a2p_evaluation_sid
            ).fetch()
            print("[GET] Trusted Product Evaluation:", a2p_evaluation)
        else:
            a2p_evaluation = client.trusthub.v1.trust_products(
                sid=trust_product.sid
            ).trust_products_evaluations.create(
                policy_sid=trust_product.policy_sid
            )

            local_verification.a2p_evaluation_sid = a2p_evaluation.sid
            local_verification.save()
            print("[CREATE] Trusted Product Evaluation:", a2p_evaluation)

        print("[CREATE END] A2P Trusted Product Evaluation")

        print("===============================================================================")


        # ============================================================
        # 15. GET EVALUATION RESULT
        # ============================================================
        print("[GET START] A2P Trausted Product Evaluation Result")
        a2p_evaluation = client.trusthub.v1.trust_products(
            sid=trust_product.sid
        ).trust_products_evaluations(
            sid=local_verification.a2p_evaluation_sid
        ).fetch()
        print("[GET] A2P Trausted Product Evaluation SID:", a2p_evaluation.sid)
        print("[GET] A2P Trausted Product Evaluation Status:", a2p_evaluation.status)
        print("[GET] A2P Trausted Product Evaluation Results:", a2p_evaluation.results)
        try:
            print("[GET] A2P Trausted Product Evaluation Whole Data:", A2PEvaluationSerializer(a2p_evaluation))
        except:
            pass
        print("[GET END] A2P Trausted Product Evaluation Result")

        print("===============================================================================")


        # ============================================================
        # 16. SUBMIT SECONDARY CUSTOMER PROFILE
        # ============================================================
        print("[UPDATE START] A2P Trusted Product")
        if a2p_evaluation.status == "compliant":
            a2p_trust_product = client.trusthub.v1.trust_products(
                sid=trust_product.sid
            ).fetch()
            print("a2p_trust_product: ", a2p_trust_product.__dict__)
            if a2p_trust_product.status == "draft":
                print("a2p update status")
                a2p_trust_product.update(status="pending-review")

            print("[UPDATE] A2P Trusted Product:", a2p_trust_product.__dict__)
            print("[UPDATE] A2P Trusted Product Status:", a2p_trust_product.status)
        else:
            print("[SKIP] Secondary Customer Profile is not compliant")
            print("[SKIP] Evaluation Status:", a2p_evaluation.status)
            print("[SKIP] Evaluation Results:", a2p_evaluation.results)

        print("[UPDATE END] A2P Trusted Product")



        print("===========================================================")
        print("END Verification A2P Trusted Product")
        print("===========================================================")

        return A2PProfileSerializer(trust_product)

    def verification_brand_registration(self, data):
        provider = self.organization.provider_account
        client = Client(provider.account_sid, provider.auth_token)
        local_verification = self.local_verification

        try:
            if not local_verification.customer_profile_sid:
                raise ValueError("Customer Profile SID is required.")

            if not local_verification.a2p_profile_sid:
                raise ValueError("A2P Profile SID is required.")

            print("[REGISTER START] Brand Registration")
            if local_verification.a2p_brand_sid:
                brand = client.messaging.v1.brand_registrations(sid=local_verification.a2p_brand_sid).fetch()
            else:
                brand = client.messaging.v1.brand_registrations.create(
                    customer_profile_bundle_sid=local_verification.customer_profile_sid,
                    a2p_profile_bundle_sid=local_verification.a2p_profile_sid,
                    # brand_type=data.get("brand_type", ""),
                )
                local_verification.a2p_brand_sid = brand.sid
                local_verification.save()
            brand_serializer = BrandSerializer(brand)
            print("[REGISTER END] Brand Registration")
            return brand_serializer
        except TwilioRestException as e:
            print(f"[REGISTER ERROR] {str(e)}")
            raise
        except Exception as e:
            print(f"[REGISTER ERROR] {str(e)}")
            raise


    def get_phone_messaging_service_and_assign(self, client):
        services = client.messaging.v1.services.list()
        for service in services:
            number_assigns = client.messaging.v1.services(
                service.sid
            ).phone_numbers.list()
            for assignment in number_assigns:
                if assignment.phone_number  == self.phone_number.phone_number:
                    service_data = MessageService_to_Dict(service)
                    return service, assignment
        return None
    
    def get_phone_messaging_service(self):
        provider = self.organization.provider_account
        client = Client(provider.account_sid, provider.auth_token)
        # phone_sid = self.phone_number.provider_phone_sid

        messaging_service, number_assign = self.get_phone_messaging_service_and_assign(client)
        if messaging_service and number_assign:
            return messaging_service
        else:
            messaging_service = client.messaging.v1.services.create(friendly_name=f"{self.organization.name} Messaging Service")
            return messaging_service
    
    def get_phone_number_assign_to_service(self):
        provider = self.organization.provider_account
        client = Client(provider.account_sid, provider.auth_token)
        phone_sid = self.phone_number.provider_phone_sid
        messaging_service, number_assign = self.get_phone_messaging_service_and_assign(client)
        if messaging_service and number_assign:
            return number_assign
        else:
            number_assign = client.messaging.v1.services(sid=messaging_service.sid).phone_numbers.create(
                phone_number_sid=phone_sid
            )
            return number_assign

    def verification_campaign_registration(self, data):
        provider = self.organization.provider_account
        client = Client(provider.account_sid, provider.auth_token)
        local_verification = self.local_verification
        try:
            if not local_verification.customer_profile_sid:
                raise ValueError("Customer Profile SID is required.")
            if not local_verification.a2p_profile_sid:
                raise ValueError("A2P Profile SID is required.")
            if not local_verification.a2p_brand_sid:
                raise ValueError("Brand Registration SID is required.")

            print("[CREATE/GET START] Message Service")
            if local_verification.messaging_service_sid:
                messaging_service = client.messaging.v1.services(sid=local_verification.messaging_service_sid).fetch()
            else:
                messaging_service = self.get_phone_messaging_service()
                local_verification.messaging_service_sid = messaging_service.sid
                local_verification.save()
            
            print(f"[CREATE/GET End] Message Service: {messaging_service.sid}")


            print("[REGISTER START] Campaign Registration")
            # us_app_to_person_usecase = client.messaging.v1.services(
            #     sid=local_verification.messaging_service_sid
            # ).us_app_to_person_usecases.fetch(
            #     brand_registration_sid=local_verification.a2p_brand_sid
            # )
            if local_verification.a2p_campaign_sid:
                us_app_to_person = client.messaging.v1.services(sid=messaging_service.sid).us_app_to_person(
                    sid=local_verification.a2p_campaign_sid
                ).fetch()
            else:
                us_app_to_person = client.messaging.v1.services(
                    messaging_service.sid
                ).us_app_to_person.create(
                    description=(
                        "Chesera LLC uses this messaging campaign to provide customer "
                        "support and service-related communications to customers who "
                        "initiate a conversation or request support. Messages may include "
                        "responses to customer inquiries, support updates, appointment "
                        "updates, service information, and assistance related to products "
                        "or services. No unsolicited marketing or promotional messages are sent."
                    ),
                    us_app_to_person_usecase="CUSTOMER_CARE",
                    has_embedded_links=False,
                    has_embedded_phone=False,
                    
                    message_samples=[
                        "Hi John, Thanks for contacting Chesera LLC. We received your message. This is an automated support response. A team member will assist you shortly. Reply STOP to unsubscribe. Reply HELP for help.",
                        "Hello, your appointment with Chesera LLC is confirmed for tomorrow at 2:00 PM. Please let us know if you need to reschedule. Reply STOP to opt-out.",
                        "Hi Sarah, your order #12345 has been processed and is ready for pickup. If you have any questions, just reply to this text. Text STOP to cancel messages."
                    ],
                    message_flow = (
                        """
End users opt-in to receive messages in two ways. First (Inbound SMS): Customers find our business contact number on our website or business listings and initiate the conversation by sending an SMS to our support team. Second (Verbal Consent): Customers call our support line and provide explicit verbal consent to receive SMS updates. The support representative reads a standard script asking, "Do you agree to receive SMS text messages from Chesera LLC for support, order status, and appointment updates? Message and data rates may apply." Once the customer verbally agrees, this consent is explicitly documented and logged in our secure CRM system before any outbound SMS is sent. Consent and phone numbers are strictly kept confidential and are never shared with, sold to, or distributed to any third parties or affiliates for marketing purposes.
"""
                    ),
                    opt_in_message="Welcome to Chesera LLC alerts. Msg & data rates may apply. Msg frequency varies. Reply HELP for help, STOP to cancel.",
                    opt_out_message="You have successfully opted out of Chesera LLC alerts. You will no longer receive any messages from us.",
                    help_message="Chesera LLC alerts: For support, please email cosmascheseret@gmail.com or visit our website. Reply STOP to cancel.",
                    privacy_policy_url="https://trychesera.com/privacy",
                    terms_and_conditions_url="https://trychesera.com/terms",
                    brand_registration_sid=local_verification.a2p_brand_sid,
                )
                # us_app_to_person = client.messaging.v1.services(
                #     messaging_service.sid
                # ).us_app_to_person.create(
                #     description=(
                #         "Chesera LLC uses this messaging campaign to provide customer "
                #         "support and service-related communications to customers who "
                #         "initiate a conversation or request support. Messages may include "
                #         "responses to customer inquiries, support updates, appointment "
                #         "updates, service information, and assistance related to products "
                #         "or services. No unsolicited marketing or promotional messages are sent."
                #     ),
                #     us_app_to_person_usecase="CUSTOMER_CARE",
                #     has_embedded_links=False,
                #     has_embedded_phone=False,
                #     message_samples=[
                #         (
                #             "Chesera LLC: Hi [first_name], thanks for contacting Chesera LLC. "
                #             "We received your message. This is an automated support response. "
                #             "A team member will assist you shortly. Reply STOP to unsubscribe. "
                #             "Reply HELP for help."
                #         ),
                #         (
                #             "Chesera LLC: Thanks for contacting our support team. "
                #             "We are reviewing your request and will provide an update shortly. "
                #             "Reply STOP to unsubscribe. Reply HELP for help."
                #         ),
                #         (
                #             "Chesera LLC: Your support request has been received. "
                #             "A representative will assist you with your appointment, "
                #             "service, or product-related inquiry. Reply STOP to unsubscribe."
                #         ),
                #     ],
                #     message_flow = (
                #         "Customers initiate the SMS conversation by contacting Chesera LLC "
                #         "for customer support or service-related assistance. When SMS consent "
                #         "is required, a support representative asks the customer for permission "
                #         "to receive SMS messages related to the current support request, "
                #         "including support updates, appointment updates, and responses to "
                #         "customer inquiries. The customer explicitly confirms consent before "
                #         "support SMS messages are sent. Messages are limited to customer "
                #         "support and service-related communications. No unsolicited marketing "
                #         "or promotional messages are sent. Customers can reply STOP to opt out "
                #         "and HELP for assistance."
                #     ),
                #     privacy_policy_url="https://trychesera.com/privacy",
                #     terms_and_conditions_url="https://trychesera.com/terms",
                #     brand_registration_sid=local_verification.a2p_brand_sid,
                # )

                local_verification.a2p_campaign_sid = us_app_to_person.sid
                local_verification.save()
            print("VIEW CAMPAIGN---: ", us_app_to_person.sid)
            print("[REGISTER End] Campaign Registration")

            print("[CREATE/GET START] Phone Number Assign to Message Service")
            if local_verification.messaging_service_assign_sid:
                messaging_service_assign = client.messaging.v1.services(sid=messaging_service.sid).phone_numbers(
                    sid=local_verification.messaging_service_assign_sid
                ).fetch()
            else:
                messaging_service_assign = self.get_phone_number_assign_to_service()
                local_verification.messaging_service_assign_sid = messaging_service_assign.sid
                local_verification.save()
            print(f"[CREATE/GET End] Phone Number Assign to Message Service: {messaging_service_assign.sid}")


            return us_app_to_person.sid
        except TwilioRestException as e:
            print(f"[REGISTER ERROR] {str(e)}")
            raise
        except Exception as e:
            print(f"[REGISTER ERROR] {str(e)}")
            raise
        

        
            

        






