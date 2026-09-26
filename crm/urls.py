from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ContactViewSet, LeadViewSet

router = DefaultRouter()
router.register(r"contacts", ContactViewSet, basename="contact")
router.register(r"leads", LeadViewSet, basename="lead")

urlpatterns = [
    path("", include(router.urls)),
]