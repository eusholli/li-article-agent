"""Unit tests for HumanizerModule."""
import unittest
from unittest.mock import MagicMock
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


if __name__ == "__main__":
    unittest.main()
