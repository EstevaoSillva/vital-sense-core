from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from .models import BurnoutAssessment, EmployeeRecord, RiskTriageDecision, StressInferenceSnapshot

User = get_user_model()


class EmployeeAuthFlowTests(APITestCase):
    def setUp(self):
        self.password = "SenhaSegura123"

        self.user = User.objects.create_user(
            username="funcionario.teste",
            email="funcionario@acme.com",
            password=self.password,
            name="Funcionario Teste",
        )
        self.employee = EmployeeRecord.objects.create(user=self.user)

        self.other_user = User.objects.create_user(
            username="outro.funcionario",
            email="outro@acme.com",
            password=self.password,
            name="Outro Funcionario",
        )
        self.other_employee = EmployeeRecord.objects.create(user=self.other_user)

        self.no_employee_user = User.objects.create_user(
            username="sem.perfil",
            email="semperfil@acme.com",
            password=self.password,
            name="Sem Perfil",
        )

    def _employee_login(self, username=None, email=None):
        payload = {"password": self.password}
        if username:
            payload["username"] = username
        if email:
            payload["email"] = email

        response = self.client.post(reverse("employee-login"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return response

    def _burnout_assessment_payload(self):
        return {
            "source": "manual",
            "gender": "male",
            "company_type": "service",
            "wfh_setup_available": True,
            "designation": 2,
            "resource_allocation": 6,
            "work_hours_per_week": 40,
            "sleep_hours": 7.0,
            "team_size": 8,
            "recognition_frequency": 2,
            "exhaustion_score": 3,
            "cynicism_score": 3,
            "efficacy_score": 3,
            "work_life_balance_score": 3,
            "manager_support_score": 3,
            "deadline_pressure_score": 3,
            "notes": "teste",
        }

    def test_employee_can_login_and_receive_tokens(self):
        response = self.client.post(
            reverse("employee-login"),
            {"username": self.user.username, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["employee_record_id"], self.employee.id)
        self.assertEqual(response.data["user_id"], self.user.id)
        self.assertEqual(response.data["username"], self.user.username)

    def test_burnout_assessment_requires_authentication(self):
        response = self.client.post(
            reverse("burnout-assessment"),
            self._burnout_assessment_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_burnout_assessment_forbidden_without_employee_profile(self):
        self._employee_login(username=self.no_employee_user.username)

        response = self.client.post(
            reverse("burnout-assessment"),
            self._burnout_assessment_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assessment_questions_hide_profile_fields_already_saved(self):
        self._employee_login(username=self.user.username)
        BurnoutAssessment.objects.create(
            employee=self.employee,
            source="manual",
            answers=self._burnout_assessment_payload(),
            composite_score=0.4,
            risk_level="low",
            method_version="burnout-composite-v2-harvard",
        )

        response = self.client.get(reverse("burnout-assessment-questions"), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        question_ids = {question["id"] for question in response.data}
        self.assertNotIn("gender", question_ids)
        self.assertNotIn("company_type", question_ids)
        self.assertNotIn("wfh_setup_available", question_ids)
        self.assertNotIn("designation", question_ids)
        self.assertNotIn("team_size", question_ids)
        self.assertIn("exhaustion_score", question_ids)
        self.assertIn("deadline_pressure_score", question_ids)

    def test_burnout_assessment_reuses_saved_profile_fields_for_partial_submission(self):
        self._employee_login(username=self.user.username)
        BurnoutAssessment.objects.create(
            employee=self.employee,
            source="manual",
            answers=self._burnout_assessment_payload(),
            composite_score=0.4,
            risk_level="low",
            method_version="burnout-composite-v2-harvard",
        )
        partial_payload = {
            "source": "manual",
            "resource_allocation": 7,
            "work_hours_per_week": 44,
            "sleep_hours": 6.5,
            "recognition_frequency": 1,
            "exhaustion_score": 4,
            "cynicism_score": 3,
            "efficacy_score": 2,
            "work_life_balance_score": 2,
            "manager_support_score": 3,
            "deadline_pressure_score": 4,
        }

        with patch(
            "employee.views.burn_rate_predictor.predict",
            return_value={
                "burn_rate_pred": 0.6,
                "burn_rate_min": 0.5,
                "burn_rate_max": 0.7,
                "risk": "moderate",
                "model_version": "burnout-composite-v2-harvard",
                "prediction_source": "model",
                "fallback_reason": "",
                "out_of_distribution": False,
                "ood_features": [],
                "top_factors": [],
            },
        ) as predict_mock:
            response = self.client.post(reverse("burnout-assessment"), partial_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        predicted_payload = predict_mock.call_args.args[0]
        self.assertEqual(predicted_payload["gender"], "male")
        self.assertEqual(predicted_payload["company_type"], "service")
        self.assertEqual(predicted_payload["team_size"], 8)
        latest_assessment = BurnoutAssessment.objects.latest("created_at")
        self.assertEqual(latest_assessment.answers["gender"], "male")
        self.assertEqual(latest_assessment.answers["resource_allocation"], 7)

    def test_risk_inference_falls_back_to_assessment_only_without_stress(self):
        self._employee_login(username=self.user.username)

        BurnoutAssessment.objects.create(
            employee=self.employee,
            source="manual",
            answers={"exhaustion_score": 4},
            composite_score=0.8,
            risk_level="high",
            notes="fallback test",
        )

        response = self.client.post(
            reverse("risk-inference"),
            {
                "context": {"channel": "mobile-app"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["inference_mode"], "assessment_only")
        self.assertEqual(response.data["confidence_level"], "moderate")
        self.assertEqual(response.data["stress_score"], 0.0)
        self.assertEqual(response.data["employee_record_id"], self.employee.id)
        decision = RiskTriageDecision.objects.latest("created_at")
        self.assertEqual(decision.inference_mode, "assessment_only")

    def test_risk_inference_falls_back_to_wearable_only_without_assessment(self):
        self._employee_login(username=self.user.username)

        StressInferenceSnapshot.objects.create(
            employee=self.employee,
            window_start="2026-03-20T10:00:00Z",
            window_end="2026-03-20T10:05:00Z",
            stress_score=0.7,
            risk_level="high",
            signal_quality=0.9,
            model_version="stress-heuristic-v1",
            feature_summary={"hr_mean": 95},
            trigger_recommended=True,
        )

        response = self.client.post(
            reverse("risk-inference"),
            {
                "context": {"channel": "mobile-app"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["inference_mode"], "wearable_only")
        self.assertEqual(response.data["confidence_level"], "low")
        self.assertEqual(response.data["burnout_score"], 0.0)
        self.assertEqual(response.data["employee_record_id"], self.employee.id)

    def test_risk_inference_uses_hybrid_when_both_inputs_exist(self):
        self._employee_login(email=self.user.email)

        BurnoutAssessment.objects.create(
            employee=self.employee,
            source="manual",
            answers={"exhaustion_score": 4},
            composite_score=0.8,
            risk_level="high",
            notes="hybrid test",
        )
        StressInferenceSnapshot.objects.create(
            employee=self.employee,
            window_start="2026-03-20T10:00:00Z",
            window_end="2026-03-20T10:05:00Z",
            stress_score=0.4,
            risk_level="moderate",
            signal_quality=0.9,
            model_version="stress-heuristic-v1",
            feature_summary={"hr_mean": 90},
            trigger_recommended=False,
        )

        response = self.client.post(
            reverse("risk-inference"),
            {
                "context": {"channel": "mobile-app"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["inference_mode"], "hybrid")
        self.assertEqual(response.data["confidence_level"], "high")
        self.assertEqual(response.data["employee_record_id"], self.employee.id)

    def test_wearable_ingest_falls_back_when_runtime_strategy_is_unsupported(self):
        self._employee_login(username=self.user.username)

        payload = {
            "device_id": "watch-01",
            "samples": [
                {
                    "sensor_type": "hr",
                    "recorded_at": "2026-03-20T10:00:00Z",
                    "value": 92.0,
                    "quality": 0.9,
                },
                {
                    "sensor_type": "eda",
                    "recorded_at": "2026-03-20T10:00:10Z",
                    "value": 1.2,
                    "quality": 0.8,
                },
                {
                    "sensor_type": "temp",
                    "recorded_at": "2026-03-20T10:00:20Z",
                    "value": 35.7,
                    "quality": 0.85,
                },
                {
                    "sensor_type": "hrv",
                    "recorded_at": "2026-03-20T10:00:30Z",
                    "value": 42.0,
                    "quality": 0.88,
                },
            ],
        }

        with patch.dict("os.environ", {"STRESS_RUNTIME_STRATEGY": "model"}):
            response = self.client.post(
                reverse("wearable-events-ingest"),
                payload,
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        snapshot = StressInferenceSnapshot.objects.latest("created_at")
        self.assertEqual(snapshot.feature_summary.get("runtime_strategy"), "heuristic")
        self.assertEqual(snapshot.feature_summary.get("requested_runtime_strategy"), "model")
        self.assertEqual(
            snapshot.feature_summary.get("fallback_reason"),
            "unsupported_runtime_strategy:model",
        )
