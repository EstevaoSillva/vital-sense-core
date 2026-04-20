from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    BurnoutAssessmentAPIView,
    BurnoutAssessmentQuestionsAPIView,
    BurnRatePredictAPIView,
    DashboardSummaryAPIView,
    EmployeeLoginAPIView,
    EmployeeRecordViewSet,
    RiskInferenceAPIView,
    WearableEventsIngestAPIView,
)

router = DefaultRouter()
router.register("employees", EmployeeRecordViewSet, basename="employee")

urlpatterns = [
    path("employees/login/", EmployeeLoginAPIView.as_view(), name="employee-login"),
    path("dashboard/summary", DashboardSummaryAPIView.as_view(), name="dashboard-summary"),
    path("ml/burn-rate/predict/", BurnRatePredictAPIView.as_view(), name="burn-rate-predict"),
    path("ml/stress/wearable/events/", WearableEventsIngestAPIView.as_view(), name="wearable-events-ingest"),
    path(
        "ml/burnout/assessment/questions/",
        BurnoutAssessmentQuestionsAPIView.as_view(),
        name="burnout-assessment-questions",
    ),
    path("ml/burnout/assessment/", BurnoutAssessmentAPIView.as_view(), name="burnout-assessment"),
    path("ml/risk/inference/", RiskInferenceAPIView.as_view(), name="risk-inference"),
]
urlpatterns += router.urls
