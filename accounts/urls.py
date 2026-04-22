from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import (
    AccountUserGroupViewSet,
    RecoveryPasswordViewSet,
    UserLoginAPIView,
    UserRegisterAPIView,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("user-groups", AccountUserGroupViewSet, basename="user-group")
router.register("recovery-passwords", RecoveryPasswordViewSet, basename="recovery-password")

urlpatterns = [
    path("users/register/", UserRegisterAPIView.as_view(), name="user-register"),
    path("users/login/", UserLoginAPIView.as_view(), name="user-login"),
]
urlpatterns += router.urls
