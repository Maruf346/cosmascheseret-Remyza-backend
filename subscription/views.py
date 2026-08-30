from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from accounts.choices import UserType
from .models import UserSubscription
from .serializers import UserSubscriptionSerializer


class UserSubscriptionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    serializer_class = UserSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or self.request.user.is_anonymous:
            return UserSubscription.objects.none()

        queryset = (
            UserSubscription.objects
            .select_related("user", "organization")
            .order_by("-created_at")
        )

        user = self.request.user
        if user.is_staff or user.is_superuser or user.user_type == UserType.ADMIN:
            return queryset
        return queryset.filter(user=user)

    def perform_create(self, serializer):
        serializer.save()


UserSubscriptionViewSet = extend_schema_view(
    list=extend_schema(
        tags=["User Subscriptions"],
        summary="List user subscriptions",
        description=(
            "Returns Apple/Google subscription payment records. Admin users see all users; "
            "client users see only their own records."
        ),
        responses={200: UserSubscriptionSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["User Subscriptions"],
        summary="Get user subscription details",
        description=(
            "Returns one Apple/Google subscription payment record. Admin users can retrieve any record; "
            "client users can retrieve only their own records."
        ),
        responses={200: UserSubscriptionSerializer, 404: OpenApiResponse(description="Subscription record not found.")},
    ),
    create=extend_schema(
        tags=["User Subscriptions"],
        summary="Create subscription payment record",
        description=(
            "Stores an Apple or Google in-app subscription payment record sent by the mobile app. "
            "The backend stores the record and uses active, unexpired records to unlock paid messaging."
        ),
        request=UserSubscriptionSerializer,
        responses={201: UserSubscriptionSerializer, 400: OpenApiResponse(description="Invalid Apple/Google subscription payload.")},
    ),
)(UserSubscriptionViewSet)