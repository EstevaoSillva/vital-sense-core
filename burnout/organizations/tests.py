from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Enterprise


class EnterpriseLookupTests(APITestCase):
    def setUp(self):
        Enterprise.objects.create(name="Acme Tecnologia", code="ACME", kind="company")
        Enterprise.objects.create(name="Vital Labs", code="VITAL", kind="company")
        Enterprise.objects.create(name="Empresa Inativa", code="OLD", kind="company", active=False)

    def test_lists_only_active_enterprises(self):
        response = self.client.get(reverse("enterprise-lookup"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = {item["code"] for item in response.data}
        self.assertEqual(codes, {"ACME", "VITAL"})

    def test_searches_by_name_or_code(self):
        response = self.client.get(reverse("enterprise-lookup"), {"search": "acm"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["code"], "ACME")
