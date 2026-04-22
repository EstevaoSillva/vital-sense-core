from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from employee.models import EmployeeProfile, EmployeeRecord
from organizations.models import Enterprise

from .models import EnterpriseCommercialProfile, TherapyGroup

User = get_user_model()


class EnterprisePortalAPITests(APITestCase):
    def setUp(self):
        self.enterprise = Enterprise.objects.create(name="Acme Tecnologia", code="ACME", kind="company")
        self.other_enterprise = Enterprise.objects.create(name="Outra Empresa", code="OTHER", kind="company")
        self.password = "SenhaSegura123"
        self.manager = User.objects.create_user(
            username="gestor",
            email="gestor@acme.com",
            password=self.password,
            name="Gestor Acme",
        )
        self.manager_record = EmployeeRecord.objects.create(user=self.manager, enterprise=self.enterprise)
        self.client.force_authenticate(self.manager)

    def test_company_patch_updates_enterprise_profile(self):
        response = self.client.patch(
            reverse("enterprise-company"),
            {
                "name": "Acme Tecnologia S.A.",
                "taxId": "12.345.678/0001-90",
                "contactName": "Marina Souza",
                "contactEmail": "marina@acme.com",
                "companySize": "100-500",
                "planId": "growth",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.enterprise.refresh_from_db()
        profile = EnterpriseCommercialProfile.objects.get(enterprise=self.enterprise)
        self.assertEqual(self.enterprise.name, "Acme Tecnologia S.A.")
        self.assertEqual(profile.plan_id, "growth")
        self.assertEqual(response.data["taxId"], "12.345.678/0001-90")

    def test_user_create_creates_user_employee_record_and_profile(self):
        response = self.client.post(
            reverse("enterprise-users"),
            {
                "name": "Ana Silva",
                "email": "ana@acme.com",
                "password": self.password,
                "department": "TI",
                "job_title": "Diretora",
                "regime": User.Regime.HYBRID,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="ana@acme.com")
        employee = EmployeeRecord.objects.get(user=user)
        profile = EmployeeProfile.objects.get(employee=employee)
        self.assertEqual(employee.enterprise, self.enterprise)
        self.assertEqual(profile.department, "TI")
        self.assertEqual(profile.job_title, "Diretora")
        self.assertEqual(response.data["role"], "Diretora")

    def test_therapy_group_rejects_member_from_other_enterprise(self):
        outsider = User.objects.create_user(
            username="externo",
            email="externo@other.com",
            password=self.password,
            name="Externo",
        )
        EmployeeRecord.objects.create(user=outsider, enterprise=self.other_enterprise)

        response = self.client.post(
            reverse("enterprise-therapy-groups"),
            {
                "name": "Grupo Intensivo",
                "focus": "Burnout",
                "member_user_ids": [outsider.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(TherapyGroup.objects.filter(name="Grupo Intensivo").exists())

    def test_lists_only_users_from_authenticated_enterprise(self):
        User.objects.create_user(username="sem-vinculo", email="sem@acme.com", password=self.password, name="Sem Vinculo")
        other_user = User.objects.create_user(username="outro", email="outro@other.com", password=self.password, name="Outro")
        EmployeeRecord.objects.create(user=other_user, enterprise=self.other_enterprise)

        response = self.client.get(reverse("enterprise-users"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = {item["email"] for item in response.data}
        self.assertEqual(emails, {"gestor@acme.com"})


class EnterpriseSignupTests(APITestCase):
    def test_signup_creates_user_without_enterprise_until_onboarding(self):
        response = self.client.post(
            reverse("enterprise-signup"),
            {
                "name": "Nova Gestora",
                "email": "nova@empresa.com",
                "password": "SenhaSegura123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="nova@empresa.com")
        self.assertIn("access", response.data)
        self.assertFalse(hasattr(user, "employee_record"))
