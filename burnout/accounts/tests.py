from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from employee.models import EmployeeRecord
from organizations.models import Enterprise

User = get_user_model()


class UserMobileAuthFlowTests(APITestCase):
    def setUp(self):
        self.enterprise = Enterprise.objects.create(
            name="Acme Tecnologia",
            code="ACME",
            kind="company",
        )
        self.inactive_enterprise = Enterprise.objects.create(
            name="Empresa Inativa",
            code="OLD",
            kind="company",
            active=False,
        )
        self.password = "SenhaSegura123"

    def test_register_creates_user_employee_and_tokens(self):
        response = self.client.post(
            reverse("user-register"),
            {
                "username": "novo.usuario",
                "email": "novo@acme.com",
                "password": self.password,
                "name": "Novo Usuario",
                "desired_name": "Novo",
                "enterprise_id": self.enterprise.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="novo.usuario")
        employee = EmployeeRecord.objects.get(user=user)
        self.assertEqual(employee.enterprise_id, self.enterprise.id)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user_id"], user.id)
        self.assertEqual(response.data["employee_record_id"], employee.id)
        self.assertTrue(response.data["has_employee_profile"])
        self.assertEqual(response.data["enterprise"]["id"], self.enterprise.id)

    def test_register_requires_active_enterprise(self):
        response = self.client.post(
            reverse("user-register"),
            {
                "username": "sem.empresa",
                "email": "sem@acme.com",
                "password": self.password,
                "name": "Sem Empresa",
                "enterprise_id": self.inactive_enterprise.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="sem.empresa").exists())

    def test_register_rejects_duplicate_email_without_creating_employee(self):
        User.objects.create_user(
            username="existente",
            email="duplicado@acme.com",
            password=self.password,
            name="Existente",
        )

        response = self.client.post(
            reverse("user-register"),
            {
                "username": "novo.duplicado",
                "email": "duplicado@acme.com",
                "password": self.password,
                "name": "Novo Duplicado",
                "enterprise_id": self.enterprise.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="novo.duplicado").exists())

    def test_login_returns_employee_and_enterprise(self):
        user = User.objects.create_user(
            username="funcionario",
            email="funcionario@acme.com",
            password=self.password,
            name="Funcionario",
        )
        employee = EmployeeRecord.objects.create(user=user, enterprise=self.enterprise)

        response = self.client.post(
            reverse("user-login"),
            {"email": user.email, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user_id"], user.id)
        self.assertEqual(response.data["employee_record_id"], employee.id)
        self.assertEqual(response.data["enterprise"]["code"], self.enterprise.code)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_rejects_user_without_employee_enterprise(self):
        user = User.objects.create_user(
            username="legado",
            email="legado@acme.com",
            password=self.password,
            name="Legado",
        )

        response = self.client.post(
            reverse("user-login"),
            {"email": user.email, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
