from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from datetime import timedelta
from unittest.mock import patch

from enterprise.models import Enterprise

from .models import (
    Article,
    ArticleSection,
    BurnoutAssessment,
    EmployeeProfile,
    EmployeeRecord,
    MobileNotification,
    Recommendation,
    RiskTriageDecision,
    StressInferenceSnapshot,
    WatchDeviceStatus,
    WearableSample,
)

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

    def test_mobile_profile_returns_contract_expected_by_app(self):
        enterprise = Enterprise.objects.create(name="TechCorp Brasil", code="techcorp", kind="unit")
        self.employee.enterprise = enterprise
        self.employee.save(update_fields=["enterprise"])
        EmployeeProfile.objects.create(
            employee=self.employee,
            job_title="Analista de Dados Senior",
            work_schedule="8h as 17h - Seg a Sex",
        )
        self._employee_login(username=self.user.username)

        response = self.client.get(reverse("mobile-profile"), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Funcionario Teste")
        self.assertEqual(response.data["email"], "funcionario@acme.com")
        self.assertEqual(response.data["jobTitle"], "Analista de Dados Senior")
        self.assertEqual(response.data["company"], "TechCorp Brasil")
        self.assertEqual(response.data["workSchedule"], "8h as 17h - Seg a Sex")

    def test_watch_sync_status_returns_persisted_device_state(self):
        synced_at = timezone.now()
        WatchDeviceStatus.objects.create(
            employee=self.employee,
            device_name="Pixel Watch 2",
            is_connected=True,
            battery_percent=72,
            last_sync_at=synced_at,
            syncing=False,
        )
        self._employee_login(username=self.user.username)

        response = self.client.get(reverse("watch-sync-status"), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["deviceName"], "Pixel Watch 2")
        self.assertTrue(response.data["isConnected"])
        self.assertEqual(response.data["batteryPercent"], 72)
        self.assertFalse(response.data["syncing"])
        self.assertIn("lastSyncLabel", response.data)

    def test_history_collections_and_detail_are_scoped_to_authenticated_employee(self):
        now = timezone.now()
        other_snapshot = StressInferenceSnapshot.objects.create(
            employee=self.other_employee,
            window_start=now - timedelta(minutes=20),
            window_end=now - timedelta(minutes=10),
            stress_score=0.9,
            risk_level="high",
            signal_quality=0.9,
        )
        snapshot = StressInferenceSnapshot.objects.create(
            employee=self.employee,
            window_start=now - timedelta(minutes=15),
            window_end=now,
            stress_score=0.42,
            risk_level="low",
            signal_quality=0.88,
        )
        WearableSample.objects.create(
            employee=self.employee,
            device_id="watch-01",
            sensor_type=WearableSample.SensorType.HR,
            recorded_at=now - timedelta(minutes=5),
            value=78,
            quality=0.9,
        )
        self._employee_login(username=self.user.username)

        list_response = self.client.get(reverse("collection-list"), format="json")
        detail_response = self.client.get(reverse("collection-detail", args=[str(snapshot.id)]), format="json")
        forbidden_detail_response = self.client.get(reverse("collection-detail", args=[str(other_snapshot.id)]), format="json")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in list_response.data], [str(snapshot.id)])
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["session"]["deviceName"], "watch-01")
        self.assertEqual(detail_response.data["heartRatePoints"], [78])
        self.assertEqual(forbidden_detail_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_insights_recommendations_articles_and_notifications_match_mobile_contracts(self):
        now = timezone.now()
        StressInferenceSnapshot.objects.create(
            employee=self.employee,
            window_start=now - timedelta(minutes=30),
            window_end=now - timedelta(minutes=20),
            stress_score=0.55,
            risk_level="moderate",
            signal_quality=0.7,
        )
        BurnoutAssessment.objects.create(
            employee=self.employee,
            source="manual",
            answers={"deterministic_factors": {"exhaustion": 0.8, "cynicism": 0.4}},
            composite_score=0.6,
            risk_level="moderate",
        )
        Recommendation.objects.create(
            employee=self.employee,
            title="Faca uma pausa de 15 minutos",
            description="Uma caminhada leve pode ajudar.",
            reason="Stress moderado na ultima janela",
            priority=Recommendation.Priority.HIGH,
        )
        article = Article.objects.create(
            title="5 Tecnicas de Respiracao para Crises",
            category="Bem-estar",
            summary="Respiracao controlada reduz a resposta de stress.",
            author="Equipe Vital Sense",
            read_time_minutes=5,
            watch_summary="Respire em ciclos curtos.",
        )
        ArticleSection.objects.create(article=article, heading="Respiracao 4-7-8", body="Inspire, segure e expire.", order=1)
        MobileNotification.objects.create(
            employee=self.employee,
            category="Stress",
            title="Stress elevado detectado",
            description="Considere uma pausa.",
            occurred_at=now,
        )
        self._employee_login(username=self.user.username)

        insights_response = self.client.get(reverse("insight-summary"), format="json")
        recommendations_response = self.client.get(reverse("recommendation-list"), format="json")
        articles_response = self.client.get(reverse("article-list"), format="json")
        article_response = self.client.get(reverse("article-detail", args=[str(article.id)]), format="json")
        notifications_response = self.client.get(reverse("notification-list"), format="json")

        self.assertEqual(insights_response.status_code, status.HTTP_200_OK)
        self.assertEqual(insights_response.data["weeklyStress"], [55])
        self.assertEqual(insights_response.data["burnoutRiskTrend"], [60])
        self.assertEqual(insights_response.data["criticalFactors"], ["exhaustion", "cynicism"])
        self.assertEqual(recommendations_response.status_code, status.HTTP_200_OK)
        self.assertEqual(recommendations_response.data[0]["priority"], "Alta")
        self.assertEqual(articles_response.status_code, status.HTTP_200_OK)
        self.assertEqual(articles_response.data[0]["readTimeMinutes"], 5)
        self.assertEqual(article_response.status_code, status.HTTP_200_OK)
        self.assertEqual(article_response.data["sections"][0]["heading"], "Respiracao 4-7-8")
        self.assertEqual(notifications_response.status_code, status.HTTP_200_OK)
        self.assertEqual(notifications_response.data[0]["title"], "Stress elevado detectado")

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
