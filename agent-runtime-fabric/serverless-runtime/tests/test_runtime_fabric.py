import json
import tempfile
import unittest
from pathlib import Path

from runtime_fabric import RuntimePaths, RuntimePolicy, ToolRuntime, ValidationError, dispatch


def test_policy() -> dict:
    return {
        "runtime_profile": {
            "network": {"allow_domains": ["github.com", "pypi.org", "registry.npmjs.org"]},
            "resources": {"ttl_seconds": 30, "output_limit_mb": 1},
            "tools": {
                "allowed": [
                    "clone_repo", "checkout_ref", "detect_stack", "install_node_deps", "install_python_deps",
                    "write_env_file", "start_process", "stop_process", "check_port", "http_health_check",
                    "stream_logs", "capture_preview_metadata", "export_artifacts", "run_code", "install_package",
                    "read_file", "write_file", "search_in_files", "functions_mapping", "bracket_tracker",
                    "list_directory", "export_artifact", "reset_session",
                ],
                "install_package": {"allowed_registries": ["pypi.org", "registry.npmjs.org"]},
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

    def test_detect_stack_and_env_file(self):
        repo = self.runtime._workspace("s1") / "repo"
        repo.mkdir(parents=True)
        (repo / "package.json").write_text("{}", encoding="utf-8")
        (repo / "requirements.txt").write_text("pytest\n", encoding="utf-8")
        detected = self.runtime.detect_stack("s1", "repo")
        self.assertTrue(detected["stack"]["node"])
        self.assertTrue(detected["stack"]["python"])
        env = self.runtime.write_env_file("s1", "repo", {"PORT": "3000", "DEBUG": "false"})
        self.assertTrue(Path(env["path"]).exists())

    def test_run_code_and_text_tools(self):
        self.runtime.write_file("s2", "app/main.py", "def x():\n    return 1\n")
        fns = self.runtime.functions_mapping("s2", "app/main.py")
        self.assertEqual(fns["functions"][0]["name"], "x")
        run = self.runtime.run_code("s2", "python", "print('ok')")
        self.assertEqual(run["exit_code"], 0)
        self.assertIn("ok", run["stdout"])

    def test_dispatch_audit_and_validation(self):
        _ = dispatch(self.runtime, {"tool": "detect_stack", "session_id": "ok_session", "args": {"repo_dir": "repo"}})
        ledger = self.runtime.paths.output_root / "audit-ledger.jsonl"
        rows = [json.loads(line) for line in ledger.read_text().splitlines()]
        self.assertEqual(rows[-1]["tool"], "detect_stack")
        with self.assertRaises(ValidationError):
            dispatch(self.runtime, {"tool": "detect_stack", "session_id": "../../bad", "args": {"repo_dir": "repo"}})


if __name__ == "__main__":
    unittest.main()
