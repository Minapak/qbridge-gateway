"""
Gateway Agent CLI
==================

Command-line interface for managing the SwiftQuantum Gateway Agent.

Usage:
    gateway-agent start                     # Start with defaults
    gateway-agent start --config config.yaml --port 8765
    gateway-agent status                    # Check server status
    gateway-agent register --url https://swiftquantum.com/api
"""

import argparse
import json
import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="gateway-agent",
        description="SwiftQuantum Gateway Agent — Self-hosted quantum hardware gateway",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ─── start command ───
    start_parser = subparsers.add_parser("start", help="Start the gateway agent server")
    start_parser.add_argument(
        "--config", "-c",
        default="device_config.yaml",
        help="Path to device configuration file (YAML or JSON)",
    )
    start_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    start_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8765,
        help="Port to listen on (default: 8765)",
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
        default="http://localhost:8765",
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
        default="device_config.yaml",
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

    if args.command == "start":
        cmd_start(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "register":
        cmd_register(args)


def cmd_start(args):
    """Start the gateway agent server."""
    from .server import GatewayServer

    print("=" * 60)
    print("  SwiftQuantum Gateway Agent v1.0.0")
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
