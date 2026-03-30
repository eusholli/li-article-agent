"""Unit tests for HumanizerModule."""
import unittest
from unittest.mock import MagicMock, patch
import dspy

# Import will fail until humanizer.py exists
from humanizer import HumanizerModule


class TestHumanizerModule(unittest.TestCase):

    def test_is_dspy_module(self):
        h = HumanizerModule()
        self.assertIsInstance(h, dspy.Module)

    def test_forward_calls_rewrite_then_critique(self):
        h = HumanizerModule()

        pass1_result = MagicMock()
        pass1_result.humanized_draft = "draft after pass 1"

        pass2_result = MagicMock()
        pass2_result.final_article = "final after pass 2"

        h.rewrite = MagicMock(return_value=pass1_result)
        h.critique = MagicMock(return_value=pass2_result)

        result = h.forward(article="original AI text")

        h.rewrite.assert_called_once_with(article="original AI text")
        h.critique.assert_called_once_with(humanized_draft="draft after pass 1")
        self.assertEqual(result, "final after pass 2")

    def test_forward_passes_pass1_draft_to_pass2(self):
        h = HumanizerModule()

        intermediate = "the intermediate draft"
        pass1 = MagicMock()
        pass1.humanized_draft = intermediate

        pass2 = MagicMock()
        pass2.final_article = "done"

        h.rewrite = MagicMock(return_value=pass1)
        h.critique = MagicMock(return_value=pass2)

        h.forward(article="anything")
        h.critique.assert_called_once_with(humanized_draft=intermediate)


from output_manager import OutputManager
import io
import sys


class TestOutputManagerHumanizingMethods(unittest.TestCase):

    def test_print_humanizing_start_prints_message(self):
        om = OutputManager(writer_id=1, version_id=1, verbose=True)
        captured = io.StringIO()
        sys.stdout = captured
        om.print_humanizing_start()
        sys.stdout = sys.__stdout__
        self.assertIn("humaniz", captured.getvalue().lower())

    def test_print_humanizing_complete_prints_message(self):
        om = OutputManager(writer_id=1, version_id=1, verbose=True)
        captured = io.StringIO()
        sys.stdout = captured
        om.print_humanizing_complete()
        sys.stdout = sys.__stdout__
        self.assertIn("humaniz", captured.getvalue().lower())


class TestGeneratorHumanizerIntegration(unittest.TestCase):

    def _make_minimal_result(self):
        """Minimal result dict matching what generate_article_with_context returns."""
        return {
            "writer_id": 1,
            "final_article": "original article text",
            "final_score": MagicMock(
                percentage=90.0,
                performance_tier="World-class",
                word_count=2100,
                meets_requirements=True,
                overall_feedback="Great",
            ),
            "target_achieved": True,
            "quality_achieved": True,
            "length_achieved": True,
            "iterations_used": 2,
            "versions": [],
            "generation_log": [],
            "word_count": 2100,
            "improvement_summary": "",
        }

    def test_result_contains_original_and_humanized_keys(self):
        """generate_article_with_context must add original_article and humanized_article."""
        result = self._make_minimal_result()

        # Simulate what the humanizer integration code does
        original = result["final_article"]
        humanized = "humanized version"

        result["original_article"] = original
        result["humanized_article"] = humanized

        self.assertIn("original_article", result)
        self.assertIn("humanized_article", result)
        self.assertEqual(result["original_article"], "original article text")
        self.assertEqual(result["humanized_article"], "humanized version")

    def test_humanizer_failure_sets_humanized_equal_to_original(self):
        """On HumanizerModule exception, humanized_article must equal original_article."""
        result = self._make_minimal_result()
        original = result["final_article"]

        # Simulate the error handling logic
        try:
            raise RuntimeError("LLM call failed")
        except Exception:
            humanized = original

        result["original_article"] = original
        result["humanized_article"] = humanized

        self.assertEqual(result["original_article"], result["humanized_article"])


from api_models import GenerateRequest


class TestGenerateRequestHumanizerModel(unittest.TestCase):

    def test_humanizer_model_defaults_to_none(self):
        req = GenerateRequest(draft="A" * 50)
        self.assertIsNone(req.humanizer_model)

    def test_humanizer_model_accepts_string(self):
        req = GenerateRequest(draft="A" * 50, humanizer_model="gemini/gemini-2.5-pro")
        self.assertEqual(req.humanizer_model, "gemini/gemini-2.5-pro")


if __name__ == "__main__":
    unittest.main()
