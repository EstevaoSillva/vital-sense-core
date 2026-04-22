from django.urls import path

from .views import (
    EnterpriseCompanyAPIView,
    EnterpriseDashboardAPIView,
    EnterpriseRecommendationListAPIView,
    EnterpriseSignupAPIView,
    EnterpriseUserListCreateAPIView,
    TherapyGroupListCreateAPIView,
)

urlpatterns = [
    path("signup/", EnterpriseSignupAPIView.as_view(), name="enterprise-signup"),
    path("company/", EnterpriseCompanyAPIView.as_view(), name="enterprise-company"),
    path("dashboard/", EnterpriseDashboardAPIView.as_view(), name="enterprise-dashboard"),
    path("users/", EnterpriseUserListCreateAPIView.as_view(), name="enterprise-users"),
    path("recommendations/", EnterpriseRecommendationListAPIView.as_view(), name="enterprise-recommendations"),
    path("therapy-groups/", TherapyGroupListCreateAPIView.as_view(), name="enterprise-therapy-groups"),
]
