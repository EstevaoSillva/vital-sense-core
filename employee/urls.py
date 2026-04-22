from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ArticleDetailAPIView,
    ArticleListAPIView,
    BurnoutAssessmentAPIView,
    BurnoutAssessmentQuestionsAPIView,
    BurnRatePredictAPIView,
    CollectionDetailAPIView,
    CollectionListAPIView,
    DashboardSummaryAPIView,
    EmployeeLoginAPIView,
    EmployeeRecordViewSet,
    InsightSummaryAPIView,
    NotificationListAPIView,
    RecommendationListAPIView,
    RiskInferenceAPIView,
    UserProfileAPIView,
    WearableEventsIngestAPIView,
    WatchSyncStatusAPIView,
)

router = DefaultRouter()
router.register("employees", EmployeeRecordViewSet, basename="employee")

urlpatterns = [
    path("employees/login/", EmployeeLoginAPIView.as_view(), name="employee-login"),
    path("dashboard/summary", DashboardSummaryAPIView.as_view(), name="dashboard-summary"),
    path("profile", UserProfileAPIView.as_view(), name="mobile-profile"),
    path("sync/status", WatchSyncStatusAPIView.as_view(), name="watch-sync-status"),
    path("history/collections", CollectionListAPIView.as_view(), name="collection-list"),
    path("history/collections/<str:collection_id>", CollectionDetailAPIView.as_view(), name="collection-detail"),
    path("insights", InsightSummaryAPIView.as_view(), name="insight-summary"),
    path("recommendations", RecommendationListAPIView.as_view(), name="recommendation-list"),
    path("content/articles", ArticleListAPIView.as_view(), name="article-list"),
    path("content/articles/<str:article_id>", ArticleDetailAPIView.as_view(), name="article-detail"),
    path("notifications", NotificationListAPIView.as_view(), name="notification-list"),
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
