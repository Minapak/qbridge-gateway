"""
Tests for gateway_agent.cli — Command-line interface
======================================================

Covers:
- Argument parsing for init, start, status, register commands
- Default values for all arguments
- cmd_init config generation
- cmd_start invocation
- cmd_status success and failure
- cmd_register success and failure
- No-command behavior (help/exit)
- Log level configuration
"""

import json
import sys
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest

from gateway_agent.cli import main, cmd_init, cmd_start, cmd_status, cmd_register


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Argument Parsing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCLIArgumentParsing:

    def test_no_command_exits(self):
        """Running with no command should exit with code 1."""
        with patch("sys.argv", ["qbridge-gateway"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_init_defaults(self):
        """Init command should use default config path."""
        with patch("sys.argv", ["qbridge-gateway", "init"]):
            with patch("gateway_agent.cli.cmd_init") as mock_init:
                main()
                args = mock_init.call_args[0][0]
                assert args.config == "config.json"
                assert args.force is False

    def test_init_custom_config(self):
        with patch("sys.argv", ["qbridge-gateway", "init", "--config", "my_config.json"]):
            with patch("gateway_agent.cli.cmd_init") as mock_init:
                main()
                args = mock_init.call_args[0][0]
                assert args.config == "my_config.json"

    def test_init_force_flag(self):
        with patch("sys.argv", ["qbridge-gateway", "init", "--force"]):
            with patch("gateway_agent.cli.cmd_init") as mock_init:
                main()
                args = mock_init.call_args[0][0]
                assert args.force is True

    def test_start_defaults(self):
        """Start command should use default config, host, port."""
        with patch("sys.argv", ["qbridge-gateway", "start"]):
            with patch("gateway_agent.cli.cmd_start") as mock_start:
                main()
                args = mock_start.call_args[0][0]
                assert args.config == "config.json"
                assert args.host == "0.0.0.0"
                assert args.port == 8090
                assert args.reload is False
                assert args.log_level == "INFO"

    def test_start_custom_args(self):
        with patch("sys.argv", [
            "qbridge-gateway", "start",
            "--config", "custom.yaml",
            "--host", "127.0.0.1",
            "--port", "9999",
            "--reload",
            "--log-level", "DEBUG",
        ]):
            with patch("gateway_agent.cli.cmd_start") as mock_start:
                main()
                args = mock_start.call_args[0][0]
                assert args.config == "custom.yaml"
                assert args.host == "127.0.0.1"
                assert args.port == 9999
                assert args.reload is True
                assert args.log_level == "DEBUG"

    def test_start_short_flags(self):
        with patch("sys.argv", [
            "qbridge-gateway", "start",
            "-c", "short.yaml",
            "-p", "7777",
        ]):
            with patch("gateway_agent.cli.cmd_start") as mock_start:
                main()
                args = mock_start.call_args[0][0]
                assert args.config == "short.yaml"
                assert args.port == 7777

    def test_status_defaults(self):
        with patch("sys.argv", ["qbridge-gateway", "status"]):
            with patch("gateway_agent.cli.cmd_status") as mock_status:
                main()
                args = mock_status.call_args[0][0]
                assert args.url == "http://localhost:8090"

    def test_status_custom_url(self):
        with patch("sys.argv", ["qbridge-gateway", "status", "--url", "http://myhost:9000"]):
            with patch("gateway_agent.cli.cmd_status") as mock_status:
                main()
                args = mock_status.call_args[0][0]
                assert args.url == "http://myhost:9000"

    def test_register_requires_url(self):
        """Register command requires --url."""
        with patch("sys.argv", ["qbridge-gateway", "register"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0

    def test_register_with_url(self):
        with patch("sys.argv", [
            "qbridge-gateway", "register",
            "--url", "https://api.swiftquantum.tech",
        ]):
            with patch("gateway_agent.cli.cmd_register") as mock_register:
                main()
                args = mock_register.call_args[0][0]
                assert args.url == "https://api.swiftquantum.tech"
                assert args.token is None

    def test_register_with_token(self):
        with patch("sys.argv", [
            "qbridge-gateway", "register",
            "--url", "https://api.swiftquantum.tech",
            "--token", "mytoken123",
        ]):
            with patch("gateway_agent.cli.cmd_register") as mock_register:
                main()
                args = mock_register.call_args[0][0]
                assert args.token == "mytoken123"

    def test_register_short_config(self):
        with patch("sys.argv", [
            "qbridge-gateway", "register",
            "--url", "https://api.example.com",
            "-c", "alt_config.yaml",
        ]):
            with patch("gateway_agent.cli.cmd_register") as mock_register:
                main()
                args = mock_register.call_args[0][0]
                assert args.config == "alt_config.yaml"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  cmd_init
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCmdInit:

    def test_cmd_init_creates_json_config(self, tmp_path):
        config_path = str(tmp_path / "config.json")
        args = MagicMock()
        args.config = config_path
        args.force = False

        cmd_init(args)

        with open(config_path) as f:
            config = json.load(f)
        assert config["server"]["port"] == 8090
        assert config["server"]["name"] == "my-gateway"
        assert config["device"]["name"] == "local_simulator"
        assert config["device"]["num_qubits"] == 20
        assert "auth" in config
        assert "registration" in config

    def test_cmd_init_refuses_overwrite_without_force(self, tmp_path, capsys):
        config_path = str(tmp_path / "config.json")
        with open(config_path, "w") as f:
            f.write("{}")

        args = MagicMock()
        args.config = config_path
        args.force = False

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            cmd_init(args)

        captured = capsys.readouterr()
        assert "already exists" in captured.out

    def test_cmd_init_overwrites_with_force(self, tmp_path):
        config_path = str(tmp_path / "config.json")
        with open(config_path, "w") as f:
            f.write("{}")

        args = MagicMock()
        args.config = config_path
        args.force = True

        cmd_init(args)

        with open(config_path) as f:
            config = json.load(f)
        assert config["server"]["port"] == 8090

    def test_cmd_init_prints_next_steps(self, tmp_path, capsys):
        config_path = str(tmp_path / "config.json")
        args = MagicMock()
        args.config = config_path
        args.force = False

        cmd_init(args)

        captured = capsys.readouterr()
        assert "Config file created" in captured.out
        assert "qbridge-gateway start" in captured.out


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  cmd_start
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCmdStart:

    def test_cmd_start_creates_server_and_starts(self):
        args = MagicMock()
        args.config = "config.json"
        args.host = "0.0.0.0"
        args.port = 8090
        args.reload = False

        with patch("gateway_agent.server.GatewayServer") as MockServer:
            mock_instance = MagicMock()
            MockServer.return_value = mock_instance
            cmd_start(args)
            MockServer.assert_called_once_with(config_path="config.json")
            mock_instance.start.assert_called_once_with(
                host="0.0.0.0", port=8090, reload=False,
            )

    def test_cmd_start_with_reload(self):
        args = MagicMock()
        args.config = "config.yaml"
        args.host = "127.0.0.1"
        args.port = 3000
        args.reload = True

        with patch("gateway_agent.server.GatewayServer") as MockServer:
            mock_instance = MagicMock()
            MockServer.return_value = mock_instance
            cmd_start(args)
            mock_instance.start.assert_called_once_with(
                host="127.0.0.1", port=3000, reload=True,
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  cmd_status
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCmdStatus:

    def test_cmd_status_success(self, capsys):
        health_data = {
            "status": "healthy",
            "server_name": "test_gw",
            "version": "1.2.0",
            "uptime_seconds": 123.4,
            "device": {
                "device": "local_simulator",
                "num_qubits": 20,
                "jobs_completed": 5,
            },
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(health_data).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        args = MagicMock()
        args.url = "http://localhost:8090"

        with patch("urllib.request.urlopen", return_value=mock_response):
            cmd_status(args)

        captured = capsys.readouterr()
        assert "healthy" in captured.out
        assert "test_gw" in captured.out
        assert "1.2.0" in captured.out

    def test_cmd_status_failure(self):
        args = MagicMock()
        args.url = "http://nonexistent-host:99999"

        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            with pytest.raises(SystemExit) as exc_info:
                cmd_status(args)
            assert exc_info.value.code == 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  cmd_register
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCmdRegister:

    def test_cmd_register_success(self, capsys, tmp_path):
        config_content = """
server:
  name: "reg_test"
  id: "gw_reg"
device:
  name: "reg_sim"
  num_qubits: 5
"""
        config_file = tmp_path / "reg_config.yaml"
        config_file.write_text(config_content)

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"registered": True}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        args = MagicMock()
        args.url = "https://api.swiftquantum.tech"
        args.config = str(config_file)
        args.token = "test-token"

        with patch("urllib.request.urlopen", return_value=mock_response):
            cmd_register(args)

        captured = capsys.readouterr()
        assert "Registration successful" in captured.out

    def test_cmd_register_failure(self):
        args = MagicMock()
        args.url = "https://api.swiftquantum.tech"
        args.config = "config.json"
        args.token = None

        with patch("gateway_agent.server.GatewayServer") as MockServer:
            MockServer.side_effect = Exception("Config error")
            with pytest.raises(SystemExit) as exc_info:
                cmd_register(args)
            assert exc_info.value.code == 1

    def test_cmd_register_without_token(self, tmp_path):
        config_content = """
server:
  name: "no_token_test"
  id: "gw_nt"
device:
  name: "nt_sim"
  num_qubits: 3
"""
        config_file = tmp_path / "nt_config.yaml"
        config_file.write_text(config_content)

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        args = MagicMock()
        args.url = "https://api.example.com"
        args.config = str(config_file)
        args.token = None

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            cmd_register(args)
            # Verify no Authorization header was sent
            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            assert "Authorization" not in req.headers


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Logging Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCLILogging:

    def test_log_level_from_args(self):
        with patch("sys.argv", ["qbridge-gateway", "start", "--log-level", "WARNING"]):
            with patch("gateway_agent.cli.cmd_start"):
                with patch("logging.basicConfig") as mock_logging:
                    main()
                    mock_logging.assert_called_once()
                    import logging
                    assert mock_logging.call_args[1]["level"] == logging.WARNING

    def test_default_log_level(self):
        with patch("sys.argv", ["qbridge-gateway", "start"]):
            with patch("gateway_agent.cli.cmd_start"):
                with patch("logging.basicConfig") as mock_logging:
                    main()
                    import logging
                    assert mock_logging.call_args[1]["level"] == logging.INFO
