import unittest
from datetime import datetime

from backend.app.services.coaching import summarize_execution
from backend.app.services.execution_quality import evaluate_execution_quality


class ExecutionQualityTests(unittest.TestCase):
    def test_easy_session_can_match_with_aerobic_zone_distribution(self):
        result = evaluate_execution_quality(
            {"workout_intent": "easy", "target_duration_min": 50},
            {"id": "a1", "type": "Run", "duration_min": 52},
            heart_rate_zones={
                "available": True,
                "zone2_pct": 58,
                "zones": [
                    {"key": "zone2", "pct": 58},
                    {"key": "zone3", "pct": 18},
                    {"key": "zone4", "pct": 4},
                    {"key": "zone5", "pct": 0},
                ],
            },
        )
        self.assertEqual(result["status"], "matched")

    def test_easy_session_can_drift_harder_than_planned(self):
        result = evaluate_execution_quality(
            {"workout_intent": "easy", "target_duration_min": 45},
            {"id": "a2", "type": "Run", "duration_min": 47},
            heart_rate_zones={
                "available": True,
                "zone2_pct": 20,
                "zones": [
                    {"key": "zone2", "pct": 20},
                    {"key": "zone3", "pct": 40},
                    {"key": "zone4", "pct": 22},
                    {"key": "zone5", "pct": 8},
                ],
            },
        )
        self.assertEqual(result["status"], "drifted")

    def test_quality_session_without_streams_is_completed_without_evidence(self):
        result = evaluate_execution_quality(
            {"workout_intent": "tempo", "target_duration_min": 60},
            {"id": "a3", "type": "Run", "duration_min": 61},
            heart_rate_zones={"available": False},
        )
        self.assertEqual(result["status"], "completed_without_evidence")

    def test_missing_planned_intent_is_unavailable(self):
        result = evaluate_execution_quality(
            {"workout_intent": None},
            {"id": "a4", "type": "Run", "duration_min": 30},
        )
        self.assertEqual(result["status"], "unavailable")

    def test_strength_session_can_match_with_enriched_detail(self):
        result = evaluate_execution_quality(
            {"workout_intent": "strength_upper"},
            {"id": "a5", "type": "WeightTraining", "duration_min": 55},
            strength_detail={
                "status": "enriched",
                "session": {
                    "total_volume_kg": 6200,
                    "exercises": [
                        {"exercise_name": "Bench Press", "work_set_count": 4, "set_count": 5},
                        {"exercise_name": "Barbell Row", "work_set_count": 4, "set_count": 4},
                        {"exercise_name": "Shoulder Press", "work_set_count": 3, "set_count": 3},
                        {"exercise_name": "Lat Pulldown", "work_set_count": 3, "set_count": 3},
                    ],
                },
            },
        )
        self.assertEqual(result["status"], "matched")

    def test_coaching_distinguishes_quality_drift_from_non_completion(self):
        today = datetime.now().date().isoformat()
        execution = summarize_execution(
            {
                "days": [
                    {
                        "date": today,
                        "session_type": "Run",
                        "comparison": {
                            "status": "linked",
                            "intent_alignment": "aligned",
                            "execution_quality": {
                                "status": "drifted",
                                "headline": "Drifted harder than planned",
                            },
                        },
                    },
                    {
                        "date": today,
                        "session_type": "Run",
                        "comparison": {
                            "status": "skipped",
                            "intent_alignment": "unknown",
                            "execution_quality": None,
                        },
                    },
                ]
            }
        )

        self.assertEqual(execution["execution_quality"]["drifted"], 1)
        self.assertEqual(execution["execution_quality"]["unavailable"], 0)
        self.assertEqual(execution["missed_sessions"], 1)
        self.assertTrue(any("drifted" in item for item in execution["key_observations"]))


if __name__ == "__main__":
    unittest.main()
