from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from core.utils.viewsets import OwnModelViewSet, OwnReadOnlyModelViewSet
from .models import SubscriptionPlan, UserSubscription, PurchaseInfo
from core.permissions import AdminWritePermission
from .serializers import SubscriptionPlanSerializer, PurchaseSubscriptionSerializer, UserSubscriptionSerializer, VerifyPurchaseSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsClientUser
from .choices import SubscriptionStatus, PaymentStatus, PlanType
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from subscription.services.purchase import SubscriptionPurchaseService, SubscriptionValidationService


class SubscriptionPlanViewSet(OwnModelViewSet):
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AdminWritePermission]
    queryset = SubscriptionPlan.objects.filter(is_active=True).order_by("price", "name")


class UserSubscriptionViewSet(OwnReadOnlyModelViewSet):
    serializer_class = UserSubscriptionSerializer
    permission_classes = [IsAuthenticated, IsClientUser]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserSubscription.objects.none()
        return (
            UserSubscription.objects
            .select_related("plan", "organization")
            .filter(
                user=self.request.user
            )
            .order_by("-created_at")
        )

    @action(detail=False, methods=["get"], url_path="current-plan")
    def current_plan(self, request):
        subscription = SubscriptionValidationService.get_current_subscription(self.request.user)
        if not subscription:
            return Response(
                {
                    "success": True,
                    "message": "No active subscription found.",
                    "data": None,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "success": True,
                "data": UserSubscriptionSerializer(subscription).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def purchase(self, request):
        with transaction.atomic():
            serializer = PurchaseSubscriptionSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            subscription_plan = serializer.context["plan"]

            if subscription_plan.plan_type == PlanType.FREE_TRAIL:
                raise ValidationError({"detail": "Free trial plan cannot be purchased."})

            subscription_data = SubscriptionPurchaseService.purchase(
                user=self.request.user,
                plan=subscription_plan,
                billing_cycle=subscription_plan.billing_type,
                # organization=self.request.user.organization or None
            )
            return Response(
                {
                    "success": True,
                    "message": "Subscription purchase initiated successfully.",
                    "data": {
                        "subscription": UserSubscriptionSerializer(subscription_data["subscription"]).data,
                        "payment_id": subscription_data["payment"].id,
                        "payment_status": subscription_data["payment"].status,
                    },
                }, status=status.HTTP_201_CREATED,
            )

    # Twilio-backed free-trial subscription route is hidden during Sent.dm migration.
    # @action(detail=False, methods=["post"], url_path="claim-free-trail")
    def claim_free_trail(self, request):
        with transaction.atomic():
            user_subscription = UserSubscription.objects.filter(
                user=self.request.user,
                plan__plan_type=PlanType.FREE_TRAIL
            )
            if user_subscription.exists():
                return Response(
                    {
                        "status": False,
                        "message": "Your free trail already claim."
                    }, status=status.HTTP_400_BAD_REQUEST
                )

            free_trail_subscription = SubscriptionPlan.objects.filter(
                plan_type=PlanType.FREE_TRAIL,
                is_active=True
            ).first()

            subscription_data = SubscriptionPurchaseService.claim_free_trail(
                user=self.request.user,
                trail_plan=free_trail_subscription,
                billing_cycle=free_trail_subscription.billing_type,
                day=free_trail_subscription.trial_days
            )
            return Response(
                {
                    "success": True,
                    "message": "Free Trail Subscription Claim successfully.",
                    "data": {
                        "subscription": UserSubscriptionSerializer(subscription_data["subscription"]).data
                    },
                }, status=status.HTTP_201_CREATED,
            )

    @action(detail=False, methods=["post"], url_path="purchase-verify")
    def purchase_verify(self, request):
        with transaction.atomic():
            serializer = VerifyPurchaseSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            subscription = serializer.validated_data["subscription_plan_uuid"]
            platform = serializer.validated_data["platform"]
            purchase_token = serializer.validated_data["purchase_token"]

            if subscription.status != SubscriptionStatus.AWAITING_PAYMENT:
                raise ValidationError("Subscription is already processed")

            payment = subscription.payments.latest("created_at")
            payment.status = PaymentStatus.SUCCEEDED
            payment.paid_at = timezone.now()
            payment.save(update_fields=["status", "paid_at"])

            subscription.status = SubscriptionStatus.ACTIVE
            subscription.save(update_fields=["status"])

            user_free_trail = UserSubscription.objects.filter(user=self.request.user, plan__plan_type=PlanType.FREE_TRAIL)
            user_free_trail.first().release_free_trial() if user_free_trail.exists() else None

            PurchaseInfo.objects.get_or_create(
                payment=payment,
                defaults={
                    "user": self.request.user,
                    "platform": platform,
                    "purchase_token": purchase_token
                }
            )

            return Response(
                {
                    "success": True,
                    "message": "Subscription activated successfully.",
                    "data": UserSubscriptionSerializer(subscription).data,
                },
                status=status.HTTP_200_OK,
            )

    # @action(detail=True, methods=["delete"])
    # def remove(self, request, pk=None):
    #     subscription = self.get_object()

    #     if subscription.status == SubscriptionStatus.ACTIVE:
    #         raise ValidationError({"detail": "Active subscription cannot be deleted."})

    #     subscription.delete()

    #     return Response(
    #         {
    #             "success": True,
    #             "message": "Subscription deleted successfully.",
    #         },
    #         status=status.HTTP_200_OK,
    #     )

SubscriptionPlanViewSet = extend_schema_view(
    list=extend_schema(
        tags=["Subscription Plans"],
        summary="List subscription plans",
        description="Returns active subscription plans ordered by price and name.",
        responses={200: SubscriptionPlanSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Subscription Plans"],
        summary="Get subscription plan",
        description="Returns one subscription plan by ID.",
        responses={200: SubscriptionPlanSerializer, 404: OpenApiResponse(description="Subscription plan not found.")},
    ),
    create=extend_schema(
        tags=["Subscription Plans"],
        summary="Create subscription plan",
        description="Creates a subscription plan. Admin access is required.",
        request=SubscriptionPlanSerializer,
        responses={201: SubscriptionPlanSerializer, 400: OpenApiResponse(description="Invalid subscription plan data.")},
    ),
    update=extend_schema(
        tags=["Subscription Plans"],
        summary="Update subscription plan",
        description="Updates a subscription plan. Admin access is required.",
        request=SubscriptionPlanSerializer,
        responses={200: SubscriptionPlanSerializer, 400: OpenApiResponse(description="Invalid subscription plan data.")},
    ),
    partial_update=extend_schema(
        tags=["Subscription Plans"],
        summary="Partially update subscription plan",
        description="Partially updates a subscription plan. Admin access is required.",
        request=SubscriptionPlanSerializer,
        responses={200: SubscriptionPlanSerializer, 400: OpenApiResponse(description="Invalid subscription plan data.")},
    ),
    destroy=extend_schema(
        tags=["Subscription Plans"],
        summary="Delete subscription plan",
        description="Deletes a subscription plan. Admin access is required.",
        responses={200: OpenApiResponse(description="Subscription plan deleted successfully.")},
    ),
)(SubscriptionPlanViewSet)

UserSubscriptionViewSet = extend_schema_view(
    list=extend_schema(
        tags=["User Subscriptions"],
        summary="List user subscriptions",
        description="Returns subscriptions belonging to the authenticated client user.",
        responses={200: UserSubscriptionSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["User Subscriptions"],
        summary="Get user subscription",
        description="Returns one subscription belonging to the authenticated client user.",
        responses={200: UserSubscriptionSerializer, 404: OpenApiResponse(description="Subscription not found.")},
    ),
    current_plan=extend_schema(
        tags=["User Subscriptions"],
        summary="Get current active plan",
        description="Returns the authenticated user's current active subscription, or null when there is no active plan.",
        responses={200: UserSubscriptionSerializer},
    ),
    purchase=extend_schema(
        tags=["Subscription Purchase"],
        summary="Start subscription purchase",
        description="Creates an awaiting-payment subscription and payment record for the selected paid plan.",
        request=PurchaseSubscriptionSerializer,
        responses={
            201: OpenApiResponse(description="Subscription purchase initiated successfully."),
            400: OpenApiResponse(description="Invalid plan, free-trial plan selected, or purchase could not be created."),
        },
    ),
    purchase_verify=extend_schema(
        tags=["Subscription Purchase"],
        summary="Verify subscription purchase",
        description="Verifies a platform purchase token/receipt and activates the pending subscription.",
        request=VerifyPurchaseSerializer,
        responses={
            200: UserSubscriptionSerializer,
            400: OpenApiResponse(description="Subscription is already processed or purchase data is invalid."),
        },
    ),
)(UserSubscriptionViewSet)
