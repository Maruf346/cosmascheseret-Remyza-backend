from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .choices import MessageTemplateType
from .models import StaticMessageTemplate
from .serializers import WelcomeMessageTemplateSerializer


class WelcomeMessageTemplateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_template(self, user):
        organization = getattr(user, "organization", None)
        if not organization:
            raise ValidationError({"organization": "Create your business profile before setting a welcome message."})
        return StaticMessageTemplate.objects.filter(
            organization=organization,
            user=user,
            template_type=MessageTemplateType.WELCOME,
        ).first()

    @extend_schema(
        tags=["Communications - Templates"],
        summary="Get welcome message",
        description="Returns the authenticated user's configured welcome message template. This text is used when automatic welcome messages are enabled in business settings.",
        responses={200: WelcomeMessageTemplateSerializer, 404: OpenApiResponse(description="Welcome message is not configured yet.")},
    )
    def get(self, request):
        template = self.get_template(request.user)
        if not template:
            raise NotFound("Welcome message is not configured yet.")
        return Response({"success": True, "data": WelcomeMessageTemplateSerializer(template).data})

    @extend_schema(
        tags=["Communications - Templates"],
        summary="Set welcome message",
        description="Creates or updates the authenticated user's welcome message template.",
        request=WelcomeMessageTemplateSerializer,
        responses={200: WelcomeMessageTemplateSerializer, 400: OpenApiResponse(description="Invalid template data.")},
    )
    def put(self, request):
        return self.upsert(request)

    @extend_schema(
        tags=["Communications - Templates"],
        summary="Partially update welcome message",
        description="Partially updates the authenticated user's welcome message template.",
        request=WelcomeMessageTemplateSerializer,
        responses={200: WelcomeMessageTemplateSerializer, 400: OpenApiResponse(description="Invalid template data.")},
    )
    def patch(self, request):
        return self.upsert(request, partial=True)

    def upsert(self, request, partial=False):
        template = self.get_template(request.user)
        serializer = WelcomeMessageTemplateSerializer(
            template,
            data=request.data,
            partial=partial,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        template = serializer.save()
        return Response(
            {"success": True, "message": "Welcome message saved successfully.", "data": WelcomeMessageTemplateSerializer(template).data},
            status=status.HTTP_200_OK,
        )