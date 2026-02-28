"""
Q-Bridge Gateway Agent CLI
============================

Command-line interface for managing the Q-Bridge Gateway Agent.

Usage:
    qbridge-gateway start                     # Start with defaults
    qbridge-gateway start --config config.json --port 8090
    qbridge-gateway init --config=config.json # Generate config file
    qbridge-gateway status                    # Check server status
    qbridge-gateway register --url https://api.swiftquantum.tech
"""

import argparse
import json
import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="qbridge-gateway",
        description="Q-Bridge Gateway Agent — Self-hosted quantum hardware gateway",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ─── init command ───
    init_parser = subparsers.add_parser("init", help="Generate a config file template")
    init_parser.add_argument(
        "--config", "-c",
        default="config.json",
        help="Path to write the config file (default: config.json)",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config file without prompting",
    )

    # ─── start command ───
    start_parser = subparsers.add_parser("start", help="Start the gateway agent server")
    start_parser.add_argument(
        "--config", "-c",
        default="config.json",
        help="Path to device configuration file (JSON or YAML)",
    )
    start_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    start_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8090,
        help="Port to listen on (default: 8090)",
    )
    start_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    start_parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    # ─── status command ───
    status_parser = subparsers.add_parser("status", help="Check gateway agent status")
    status_parser.add_argument(
        "--url",
        default="http://localhost:8090",
        help="Gateway agent URL",
    )

    # ─── register command ───
    register_parser = subparsers.add_parser(
        "register",
        help="Register this gateway with SwiftQuantum cloud",
    )
    register_parser.add_argument(
        "--url",
        required=True,
        help="SwiftQuantum API URL for registration",
    )
    register_parser.add_argument(
        "--token",
        help="Authentication token",
    )
    register_parser.add_argument(
        "--config", "-c",
        default="config.json",
        help="Device config file path",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Setup logging
    log_level = getattr(args, "log_level", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if args.command == "init":
        cmd_init(args)
    elif args.command == "start":
        cmd_start(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "register":
        cmd_register(args)


def cmd_init(args):
    """Generate a config file template."""
    config_path = args.config

    if os.path.exists(config_path) and not getattr(args, "force", False):
        if sys.stdin.isatty():
            response = input(f"File '{config_path}' already exists. Overwrite? [y/N]: ")
            if response.lower() not in ("y", "yes"):
                print("Aborted.")
                return
        else:
            print(f"File '{config_path}' already exists. Use --force to overwrite.")
            return

    template = {
        "server": {
            "name": "my-gateway",
            "id": "gw_001",
            "host": "0.0.0.0",
            "port": 8090,
        },
        "device": {
            "name": "local_simulator",
            "num_qubits": 20,
            "technology": "simulator",
            "connectivity": "full",
            "supported_gates": [
                "h", "x", "y", "z", "cx", "rx", "ry", "rz",
                "s", "t", "swap", "cz", "ccx", "id", "measure",
            ],
            "max_shots": 1000000,
        },
        "auth": {
            "enabled": False,
            "token": "",
        },
        "registration": {
            "auto_register": False,
            "swiftquantum_url": "https://api.swiftquantum.tech",
            "api_key": "",
        },
    }

    with open(config_path, "w") as f:
        json.dump(template, f, indent=2)
        f.write("\n")

    print(f"Config file created: {config_path}")
    print()
    print("Next steps:")
    print(f"  1. Edit {config_path} to match your hardware")
    print(f"  2. Run: qbridge-gateway start --config={config_path}")


def cmd_start(args):
    """Start the gateway agent server."""
    from .server import GatewayServer

    print("=" * 60)
    print("  Q-Bridge Gateway Agent v1.2.0")
    print("=" * 60)
    print(f"  Config:  {args.config}")
    print(f"  Host:    {args.host}")
    print(f"  Port:    {args.port}")
    print("=" * 60)
    print()

    server = GatewayServer(config_path=args.config)
    server.start(host=args.host, port=args.port, reload=args.reload)


def cmd_status(args):
    """Check gateway agent health status."""
    try:
        import urllib.request

        url = f"{args.url.rstrip('/')}/gateway/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        print("Gateway Agent Status")
        print("=" * 40)
        print(f"  Status:        {data.get('status', 'unknown')}")
        print(f"  Server:        {data.get('server_name', 'unknown')}")
        print(f"  Version:       {data.get('version', 'unknown')}")
        print(f"  Uptime:        {data.get('uptime_seconds', 0):.1f}s")

        device = data.get("device", {})
        if device:
            print(f"  Device:        {device.get('device', 'unknown')}")
            print(f"  Qubits:        {device.get('num_qubits', 0)}")
            print(f"  Jobs Done:     {device.get('jobs_completed', 0)}")

        print("=" * 40)

    except Exception as e:
        print(f"Error connecting to gateway agent at {args.url}: {e}")
        sys.exit(1)


def cmd_register(args):
    """Register gateway with SwiftQuantum cloud."""
    try:
        from .server import GatewayServer

        server = GatewayServer(config_path=args.config)
        device_info = server.device.get_device_info()

        registration = {
            "server_name": server.server_name,
            "server_id": server.server_id,
            "device": {
                "name": device_info.name,
                "num_qubits": device_info.num_qubits,
                "technology": device_info.technology,
                "connectivity": device_info.connectivity,
                "supported_gates": device_info.supported_gates,
            },
            "protocol_version": "1.0",
        }

        import urllib.request

        url = f"{args.url.rstrip('/')}/gateway/register"
        data = json.dumps(registration).encode()
        headers = {"Content-Type": "application/json"}
        if args.token:
            headers["Authorization"] = f"Bearer {args.token}"

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())

        print("Registration successful!")
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Registration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
