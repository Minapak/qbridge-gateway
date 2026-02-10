# Changelog

All notable changes to Gateway Agent will be documented in this file.

## [1.0.0] - 2026-02-10

### Added - Initial Release
- **gRPC Device Gateway Agent**: Core gateway agent for quantum backend communication
- **Device Configuration**: YAML-based device configuration (device_config.yaml)
- **Provider Discovery**: Dynamic quantum provider/backend discovery
- **Job Execution**: Submit quantum circuits to backend devices
- **Job Submission Alias**: POST /submit endpoint for simplified job submission
- **Environment Configuration**: .env.example with required settings
- **Python Package**: pyproject.toml with project metadata and dependencies

### Files
- gateway_agent/ - Core agent module
- device_config.yaml - Device configuration
- pyproject.toml - Package configuration
- requirements.txt - Python dependencies
- .env.example - Environment template
- README.md - Project documentation
