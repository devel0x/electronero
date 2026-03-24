import json
import tempfile
import unittest
from pathlib import Path

from runtime_fabric import RuntimePaths, RuntimePolicy, ToolRuntime, ValidationError, dispatch


def test_policy() -> dict:
    return {
        "runtime_profile": {
            "network": {"allow_domains": ["pypi.org", "registry.npmjs.org"]},
            "resources": {
                "ttl_seconds": 10,
                "output_limit_mb": 1,
                "memory_limit_mb": 256,
                "cpu_quota": "1",
            },
            "tools": {
                "allowed": [
                    "run_code",
                    "write_file",
                    "read_file",
                    "search_in_files",
                    "functions_mapping",
                    "bracket_tracker",
                    "list_directory",
                    "export_artifact",
                    "install_package",
                    "reset_session",
                ],
                "install_package": {
                    "allowed_registries": ["pypi.org", "registry.npmjs.org"],
                    "require_version_pin": True,
                },
            },
        }
    }


class RuntimeFabricTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        paths = RuntimePaths(
            readonly_base=root / "readonly-base",
            workspaces_root=root / "workspaces",
            tmp_root=root / "tmp",
            output_root=root / "output",
            cache_root=root / "cache",
        )
        self.runtime = ToolRuntime(RuntimePolicy(test_policy()), paths)

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_read_search(self):
        self.runtime.write_file("s1", "app/main.py", "def hello():\n    return 1\n")
        content = self.runtime.read_file("s1", "app/main.py")["content"]
        self.assertIn("def hello", content)

        matches = self.runtime.search_in_files("s1", r"return", "app")
        self.assertEqual(len(matches["matches"]), 1)

    def test_function_map_and_bracket_tracker(self):
        self.runtime.write_file("s2", "code.js", "function ping() { return 1; }\n")
        fmap = self.runtime.functions_mapping("s2", "code.js")
        self.assertEqual(fmap["functions"][0]["name"], "ping")

        self.runtime.write_file("s2", "bad.py", "print((1+2)\n")
        bt = self.runtime.bracket_tracker("s2", "bad.py")
        self.assertFalse(bt["balanced"])

    def test_run_python_and_audit(self):
        req = {
            "tool": "run_code",
            "session_id": "s3",
            "args": {"language": "python", "code": "print('ok')"},
        }
        res = dispatch(self.runtime, req)
        self.assertEqual(res["exit_code"], 0)
        self.assertIn("ok", res["stdout"])

        ledger = self.runtime.paths.output_root / "audit-ledger.jsonl"
        self.assertTrue(ledger.exists())
        rows = [json.loads(line) for line in ledger.read_text().splitlines()]
        self.assertEqual(rows[-1]["tool"], "run_code")
        self.assertEqual(rows[-1]["status"], "ok")

    def test_invalid_session_id_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.runtime.write_file("../../evil", "x.txt", "nope")


if __name__ == "__main__":
    unittest.main()
