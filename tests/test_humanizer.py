"""Unit tests for HumanizerModule and related classes."""
import io
import os
import queue
import sys
import unittest
from unittest.mock import MagicMock, patch

import dspy

from humanizer import (
    HumanizerModule,
    UndetectableDetectorApi,
    UndetectableHumanizerApi,
)


class TestHumanizerModule(unittest.TestCase):

    def test_is_dspy_module(self):
        h = HumanizerModule()
        self.assertIsInstance(h, dspy.Module)

    def test_forward_returns_dict_with_humanized_article(self):
        h = HumanizerModule()

        pass1_result = MagicMock()
        pass1_result.humanized_draft = "draft after pass 1"

        pass3_result = MagicMock()
        pass3_result.final_article = "final after pass 3"

        h.rewrite = MagicMock(return_value=pass1_result)
        h.restore = MagicMock(return_value=pass3_result)

        result = h.forward(article="original AI text")

        self.assertIsInstance(result, dict)
        self.assertIn("humanized_article", result)
        self.assertEqual(result["humanized_article"], "final after pass 3")

    def test_forward_calls_rewrite_then_restore(self):
        h = HumanizerModule()

        pass1_result = MagicMock()
        pass1_result.humanized_draft = "draft after pass 1"

        pass3_result = MagicMock()
        pass3_result.final_article = "final after pass 3"

        h.rewrite = MagicMock(return_value=pass1_result)
        h.restore = MagicMock(return_value=pass3_result)

        h.forward(article="original AI text")

        h.rewrite.assert_called_once_with(article="original AI text")
        h.restore.assert_called_once_with(humanized_draft="draft after pass 1")

    def test_forward_detection_none_when_no_api_key(self):
        """When UNDETECTABLE_API_KEY is not set, detection should be None."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("UNDETECTABLE_API_KEY", None)
            h = HumanizerModule()

        self.assertIsNone(h.humanizer_api)
        self.assertIsNone(h.detector_api)

        pass1_result = MagicMock()
        pass1_result.humanized_draft = "draft"
        pass3_result = MagicMock()
        pass3_result.final_article = "final"
        h.rewrite = MagicMock(return_value=pass1_result)
        h.restore = MagicMock(return_value=pass3_result)

        result = h.forward(article="text")
        self.assertIsNone(result["detection"])

    def test_api_instances_created_when_key_set(self):
        """When UNDETECTABLE_API_KEY is set, humanizer_api and detector_api are initialised."""
        with patch.dict(os.environ, {"UNDETECTABLE_API_KEY": "test-key-123"}):
            h = HumanizerModule()

        self.assertIsInstance(h.humanizer_api, UndetectableHumanizerApi)
        self.assertIsInstance(h.detector_api, UndetectableDetectorApi)

    def test_api_failure_falls_back_to_branded_text(self):
        """If the humanizer API raises, forward returns the Pass 1 output and no detection."""
        with patch.dict(os.environ, {"UNDETECTABLE_API_KEY": "test-key-123"}):
            h = HumanizerModule()

        pass1_result = MagicMock()
        pass1_result.humanized_draft = "branded draft"
        pass3_result = MagicMock()
        pass3_result.final_article = "final from branded"

        h.rewrite = MagicMock(return_value=pass1_result)
        h.restore = MagicMock(return_value=pass3_result)
        h.humanizer_api = MagicMock()
        h.humanizer_api.humanize.side_effect = TimeoutError("timed out")
        h.detector_api = MagicMock()
        h.detector_api.detect.side_effect = Exception("detection failed")

        result = h.forward(article="original")

        # Should not raise; should fall back gracefully
        self.assertIn("humanized_article", result)
        # restore was called with the branded draft (Pass 1 output) as fallback
        h.restore.assert_called_once_with(humanized_draft="branded draft")


class TestOutputManagerHumanizingMethods(unittest.TestCase):

    def test_print_humanizing_start_prints_message(self):
        from output_manager import OutputManager
        om = OutputManager(writer_id=1, version_id=1, verbose=True)
        captured = io.StringIO()
        sys.stdout = captured
        om.print_humanizing_start()
        sys.stdout = sys.__stdout__
        self.assertIn("humaniz", captured.getvalue().lower())

    def test_print_humanizing_complete_prints_message(self):
        from output_manager import OutputManager
        om = OutputManager(writer_id=1, version_id=1, verbose=True)
        captured = io.StringIO()
        sys.stdout = captured
        om.print_humanizing_complete()
        sys.stdout = sys.__stdout__
        self.assertIn("humaniz", captured.getvalue().lower())

    def test_print_undetectable_submitted_prints_message(self):
        from output_manager import OutputManager
        om = OutputManager(writer_id=1, version_id=1, verbose=True)
        captured = io.StringIO()
        sys.stdout = captured
        om.print_undetectable_submitted()
        sys.stdout = sys.__stdout__
        self.assertIn("undetectable", captured.getvalue().lower())

    def test_print_detection_complete_prints_scores(self):
        from output_manager import OutputManager
        om = OutputManager(writer_id=1, version_id=1, verbose=True)
        captured = io.StringIO()
        sys.stdout = captured
        om.print_detection_complete("humanized", ai_score=12.0, human_score=88.0)
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        self.assertIn("88", output)
        self.assertIn("12", output)


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

    def test_result_contains_original_humanized_and_detection_keys(self):
        """generate_article_with_context must add original_article, humanized_article, detection_scores."""
        result = self._make_minimal_result()
        original = result["final_article"]
        humanized = "humanized version"

        result["original_article"] = original
        result["humanized_article"] = humanized
        result["detection_scores"] = None

        self.assertIn("original_article", result)
        self.assertIn("humanized_article", result)
        self.assertIn("detection_scores", result)
        self.assertEqual(result["original_article"], "original article text")
        self.assertEqual(result["humanized_article"], "humanized version")

    def test_humanizer_failure_sets_humanized_equal_to_original(self):
        """On HumanizerModule exception, humanized_article must equal original_article."""
        result = self._make_minimal_result()
        original = result["final_article"]

        try:
            raise RuntimeError("LLM call failed")
        except Exception:
            humanized = original
            detection_scores = None

        result["original_article"] = original
        result["humanized_article"] = humanized
        result["detection_scores"] = detection_scores

        self.assertEqual(result["original_article"], result["humanized_article"])
        self.assertIsNone(result["detection_scores"])


from api_models import GenerateRequest


class TestGenerateRequestHumanizerModel(unittest.TestCase):

    def test_humanizer_model_defaults_to_none(self):
        req = GenerateRequest(draft="A" * 50)
        self.assertIsNone(req.humanizer_model)

    def test_humanizer_model_accepts_string(self):
        req = GenerateRequest(draft="A" * 50, humanizer_model="gemini/gemini-2.5-pro")
        self.assertEqual(req.humanizer_model, "gemini/gemini-2.5-pro")


from api import QueueOutputManager


class TestQueueOutputManagerHumanizingEvents(unittest.TestCase):

    def test_print_humanizing_start_emits_event(self):
        q = queue.Queue()
        om = QueueOutputManager(writer_id=1, progress_queue=q)
        om.print_humanizing_start()
        event = q.get_nowait()
        self.assertEqual(event["type"], "progress")
        self.assertEqual(event["stage"], "humanizing")

    def test_print_humanizing_complete_emits_event(self):
        q = queue.Queue()
        om = QueueOutputManager(writer_id=1, progress_queue=q)
        om.print_humanizing_complete()
        event = q.get_nowait()
        self.assertEqual(event["type"], "progress")
        self.assertEqual(event["stage"], "humanized")

    def test_print_undetectable_submitted_emits_event(self):
        q = queue.Queue()
        om = QueueOutputManager(writer_id=1, progress_queue=q)
        om.print_undetectable_submitted()
        event = q.get_nowait()
        self.assertEqual(event["type"], "progress")
        self.assertEqual(event["stage"], "humanizing_api")

    def test_print_undetectable_progress_includes_elapsed(self):
        q = queue.Queue()
        om = QueueOutputManager(writer_id=1, progress_queue=q)
        om.print_undetectable_progress(elapsed=30)
        event = q.get_nowait()
        self.assertEqual(event["type"], "progress")
        self.assertIn("30", event["message"])

    def test_print_detection_start_emits_event_with_which(self):
        q = queue.Queue()
        om = QueueOutputManager(writer_id=1, progress_queue=q)
        om.print_detection_start("humanized")
        event = q.get_nowait()
        self.assertEqual(event["type"], "progress")
        self.assertEqual(event["stage"], "detecting_humanized")

    def test_print_detection_complete_emits_scores(self):
        q = queue.Queue()
        om = QueueOutputManager(writer_id=1, progress_queue=q)
        om.print_detection_complete("original", ai_score=94.0, human_score=6.0)
        event = q.get_nowait()
        self.assertEqual(event["type"], "progress")
        self.assertEqual(event["stage"], "detected_original")
        self.assertIn("94", event["message"])
        self.assertIn("6", event["message"])


if __name__ == "__main__":
    unittest.main()
