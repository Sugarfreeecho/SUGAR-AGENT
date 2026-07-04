import os
import unittest
from unittest.mock import patch

from app.runtime_v2.config import runtime_v1_primary, runtime_v2_primary, runtime_version


class RuntimeConfigTests(unittest.TestCase):
    def test_runtime_version_prefers_explicit_version(self):
        with patch.dict(os.environ, {"RUNTIME_VERSION": "1", "RUNTIME_V2_ENABLED": "1"}, clear=False):
            self.assertEqual(runtime_version(), 1)
            self.assertTrue(runtime_v1_primary())
            self.assertFalse(runtime_v2_primary())

        with patch.dict(os.environ, {"RUNTIME_VERSION": "2", "RUNTIME_V2_ENABLED": "0"}, clear=False):
            self.assertEqual(runtime_version(), 2)
            self.assertFalse(runtime_v1_primary())
            self.assertTrue(runtime_v2_primary())

    def test_runtime_version_supports_legacy_enabled_flag(self):
        with patch.dict(os.environ, {"RUNTIME_V2_ENABLED": "0"}, clear=False):
            os.environ.pop("RUNTIME_VERSION", None)
            os.environ.pop("RUNTIME_version", None)
            self.assertEqual(runtime_version(), 1)

        with patch.dict(os.environ, {"RUNTIME_V2_ENABLED": "1"}, clear=False):
            os.environ.pop("RUNTIME_VERSION", None)
            os.environ.pop("RUNTIME_version", None)
            self.assertEqual(runtime_version(), 2)


if __name__ == "__main__":
    unittest.main()
