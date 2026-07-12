from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "lazarus_cli.py"
spec = importlib.util.spec_from_file_location("lazarus_cli", CLI_PATH)
assert spec and spec.loader
lazarus_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lazarus_cli)


class LazarusCliTests(unittest.TestCase):
    def test_mcp_registration_prefers_live_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            settings = root / "settings.json"
            user_config = root / ".claude.json"
            expected = "/new/run_lazarus_mcp.sh"
            old = "/old/run_lazarus_mcp.sh"
            settings.write_text(
                '{"mcpServers":{"lazarus":{"command":"/new/run_lazarus_mcp.sh"}}}',
                encoding="utf-8",
            )
            user_config.write_text(
                '{"mcpServers":{"lazarus":{"command":"/old/run_lazarus_mcp.sh"}}}',
                encoding="utf-8",
            )

            with patch.object(lazarus_cli, "MCP_SETTINGS", settings):
                with patch.object(lazarus_cli, "CLAUDE_USER_CONFIG", user_config):
                    with patch.object(lazarus_cli, "EXPECTED_MCP_PATH", expected):
                        payload = lazarus_cli.mcp_registration()

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["command"], old)
            self.assertEqual(payload["settings_command"], expected)
            self.assertEqual(payload["user_config_command"], old)

    def test_status_payload_reports_aggregate_health(self) -> None:
        with patch.object(lazarus_cli, "qdrant_alive", return_value=True):
            with patch.object(lazarus_cli, "daemon_running", return_value=(True, "123")):
                with patch.object(
                    lazarus_cli,
                    "memory_counts",
                    return_value=([{"persona": "murphy", "collection": "murphy_eternal", "count": 10, "status": "ok"}], 10),
                ):
                    with patch.object(lazarus_cli, "mcp_registration", return_value={"ok": True, "command": "/new"}):
                        with patch.object(lazarus_cli, "sync_state", return_value={"last_sync": "2026-05-28T00:00:00"}):
                            payload = lazarus_cli.status_payload()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["daemon"]["pid"], "123")
        self.assertEqual(payload["memories"]["total"], 10)


if __name__ == "__main__":
    unittest.main()
