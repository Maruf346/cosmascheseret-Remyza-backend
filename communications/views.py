from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    WelcomeMessagePresetResponseSerializer,
    WelcomeMessageSelectionSerializer,
    WelcomeMessageSelectionResponseSerializer,
    WelcomeMessageTemplateSerializer,
    WelcomeTemplatePresetSerializer,
    get_selected_welcome_template,
    save_selected_welcome_template,
)
from .welcome_templates import get_welcome_template, list_welcome_templates


class WelcomeMessageTemplateAPIView(APIView):
    """Legacy free-form welcome endpoint kept intentionally unrouted."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(status=status.HTTP_404_NOT_FOUND)

    def put(self, request):
        return Response(status=status.HTTP_404_NOT_FOUND)

    def patch(self, request):
        return Response(status=status.HTTP_404_NOT_FOUND)


class WelcomeMessagePresetAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Communications - Templates"],
        summary="Get welcome message preset templates",
        description=(
            "Returns backend-owned welcome message templates. Pass `template=professional`, "
            "`friendly`, or `casual` to fetch one preset. Without `template`, returns all presets "
            "plus the authenticated user's selected welcome template when configured."
        ),
        parameters=[OpenApiParameter("template", str, required=False, description="Preset key: professional, friendly, or casual.")],
        responses={200: WelcomeMessagePresetResponseSerializer, 400: OpenApiResponse(description="Invalid template key.")},
    )
    def get(self, request):
        template_key = (request.query_params.get("template") or "").strip().lower()
        selected = get_selected_welcome_template(request.user)

        if template_key:
            preset = get_welcome_template(template_key)
            if not preset:
                raise ValidationError({"template": "Choose one of: professional, friendly, casual."})
            return Response(
                {
                    "success": True,
                    "data": {
                        "template": preset,
                        "selected": WelcomeMessageTemplateSerializer(selected).data if selected else None,
                    },
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "success": True,
                "data": {
                    "templates": list_welcome_templates(),
                    "selected": WelcomeMessageTemplateSerializer(selected).data if selected else None,
                },
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Communications - Templates"],
        summary="Select welcome message preset",
        description="Saves one backend-owned welcome message preset for the authenticated user. Free-form welcome text is not accepted.",
        request=WelcomeMessageSelectionSerializer,
        responses={200: WelcomeMessageSelectionResponseSerializer, 400: OpenApiResponse(description="Invalid template key or missing business profile.")},
    )
    def put(self, request):
        return self.select_template(request)

    @extend_schema(
        tags=["Communications - Templates"],
        summary="Update selected welcome message preset",
        description="Updates the selected backend-owned welcome message preset. Free-form welcome text is not accepted.",
        request=WelcomeMessageSelectionSerializer,
        responses={200: WelcomeMessageSelectionResponseSerializer, 400: OpenApiResponse(description="Invalid template key or missing business profile.")},
    )
    def patch(self, request):
        return self.select_template(request)

    def select_template(self, request):
        serializer = WelcomeMessageSelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = save_selected_welcome_template(request.user, serializer.validated_data["template"])
        return Response(
            {
                "success": True,
                "message": "Welcome message template selected successfully.",
                "data": WelcomeMessageTemplateSerializer(template).data,
            },
            status=status.HTTP_200_OK,
        )
