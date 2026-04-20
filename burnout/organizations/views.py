from rest_framework import generics, permissions
from django.db.models import Q

from .models import Enterprise
from .serializers import EnterpriseLookupSerializer


class EnterpriseLookupAPIView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = EnterpriseLookupSerializer
    filter_backends = []
    pagination_class = None

    def get_queryset(self):
        queryset = Enterprise.objects.filter(active=True).order_by("name")
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
        return queryset.order_by("name").distinct()[:20]
