from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .ai_service import AIService
from .serializers import StructuredMessageRequestSerializer, StructuredMessageResponseSerializer


class StructuredMessageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["AI - Messages"],
        summary="Structure message by tone",
        description="Stateless AI helper. Accepts a tone and raw message, then returns a structured message without reading or writing database records.",
        request=StructuredMessageRequestSerializer,
        responses={200: StructuredMessageResponseSerializer, 400: OpenApiResponse(description="Invalid tone or message.")},
    )
    def post(self, request):
        serializer = StructuredMessageRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = AIService().generate_structured_message(
            tone=serializer.validated_data["tone"],
            msg=serializer.validated_data["msg"],
        )
        return Response({"success": True, "data": data}, status=status.HTTP_200_OK)