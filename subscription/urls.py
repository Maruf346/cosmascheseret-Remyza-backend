from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import UserSubscriptionViewSet


router = DefaultRouter()
router.register("user-subscription", UserSubscriptionViewSet, basename="user-subscription")

urlpatterns = [
    path("", include(router.urls)),
]