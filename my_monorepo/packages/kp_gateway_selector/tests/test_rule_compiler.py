import os
import sys
import unittest

# Ensure package root (my_monorepo/packages) is on sys.path
THIS_DIR = os.path.dirname(__file__)
PKG_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
sys.path.insert(0, PKG_ROOT)

# Import matchers to register factories
import kp_gateway_selector.gateway_selector.matchers.value_in  # noqa: F401

from kp_gateway_selector.gateway_selector.compiler.rule_compiler import compile_predicate


class TestRuleCompiler(unittest.TestCase):
    def test_value_in_simple(self):
        tree = {
            "all": [
                {"type": "VALUE_IN", "field": "api_user_id", "values": [1, 2, 3], "coerce": "int"}
            ]
        }
        pred = compile_predicate(tree)
        self.assertTrue(pred({"api_user_id": 1}))
        self.assertFalse(pred({"api_user_id": 99}))

    def test_none_wrapper(self):
        tree = {
            "none": [
                {"type": "VALUE_IN", "field": "pix_key_type", "values": ["EMAIL"], "coerce": "str"}
            ]
        }
        pred = compile_predicate(tree)
        self.assertTrue(pred({"pix_key_type": "PHONE"}))
        self.assertFalse(pred({"pix_key_type": "EMAIL"}))


if __name__ == "__main__":
    unittest.main()
