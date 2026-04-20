from rest_framework import serializers

from .models import Enterprise


class EnterpriseLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enterprise
        fields = ("id", "name", "code", "kind")
