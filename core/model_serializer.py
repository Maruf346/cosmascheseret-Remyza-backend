from rest_framework import serializers
from .models import UserFreeTrailNumber

class UserFreeTrailNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserFreeTrailNumber
        fields = "__all__"

