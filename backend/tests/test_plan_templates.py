import unittest

from backend.app.services.plans import _apply_strength_templates_to_days

PROGRAMS = {
    "programs": {
        "strength": {
            "templates": [
                {"id": "strength-c", "label": "Workout C · Wide Shoulders"},
                {"id": "strength-d", "label": "Workout D · Lower + Core", "focus_area": "lower"},
            ],
            "rotation_state": {"next_template_id": "strength-d"},
        }
    }
}


class StrengthTemplateRotationTests(unittest.TestCase):
    def test_bodyweight_lift_takes_no_template_and_the_rotation_waits(self):
        days = [
            {"date": "2026-10-31", "session_type": "strength", "title": "Bodyweight upper + core (parents' home)",
             "template_id": "strength-d", "template_label": "Workout D · Lower + Core"},
            {"date": "2026-11-02", "session_type": "strength", "title": "Strength"},
        ]
        bodyweight, next_lift = _apply_strength_templates_to_days(days, PROGRAMS, {})

        self.assertIsNone(bodyweight["template_id"])
        self.assertIsNone(bodyweight["template_label"])
        self.assertEqual(bodyweight["title"], "Bodyweight upper + core (parents' home)")
        self.assertEqual(next_lift["template_id"], "strength-d")


if __name__ == "__main__":
    unittest.main()
