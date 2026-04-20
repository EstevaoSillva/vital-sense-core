from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import AccountUserGroupFilter, RecoveryPasswordFilter, UserFilter
from .models import AccountUserGroup, RecoveryPassword, User
from .serializers import (
    AccountUserGroupSerializer,
    RecoveryPasswordSerializer,
    UserAuthOutputSerializer,
    UserLoginSerializer,
    UserRegisterSerializer,
    UserSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    queryset = User.objects.all().order_by("username")
    serializer_class = UserSerializer
    filterset_class = UserFilter
    search_fields = ("username", "email", "name", "desired_name")
    ordering_fields = (
        "id",
        "username",
        "email",
        "name",
        "is_active",
        "is_staff",
        "created_at",
        "modified_at",
    )
    ordering = ("username",)


class AccountUserGroupViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    queryset = AccountUserGroup.objects.select_related("user", "group").all().order_by("-created_at")
    serializer_class = AccountUserGroupSerializer
    filterset_class = AccountUserGroupFilter
    search_fields = ("user__username", "user__email", "group__name")
    ordering_fields = ("id", "user_id", "group_id", "active", "created_at", "modified_at")
    ordering = ("-created_at",)


class RecoveryPasswordViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    queryset = RecoveryPassword.objects.select_related("user").all().order_by("-created_at")
    serializer_class = RecoveryPasswordSerializer
    filterset_class = RecoveryPasswordFilter
    search_fields = ("user__username", "user__email", "code")
    ordering_fields = ("id", "user_id", "code", "expiration_date", "active", "created_at")
    ordering = ("-created_at",)


class UserRegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = UserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        output = UserAuthOutputSerializer(UserAuthOutputSerializer.from_user(user))
        return Response(output.data, status=status.HTTP_201_CREATED)


class UserLoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        output = UserAuthOutputSerializer(UserAuthOutputSerializer.from_user(user))
        return Response(output.data, status=status.HTTP_200_OK)