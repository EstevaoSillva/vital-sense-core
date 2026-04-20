from django.urls import path

from .views import EnterpriseLookupAPIView


urlpatterns = [
    path("enterprises/", EnterpriseLookupAPIView.as_view(), name="enterprise-lookup"),
]
