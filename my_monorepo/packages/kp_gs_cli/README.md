# KP Gateway Selector CLI

A command-line interface for managing and validating KP Gateway Selector rulesets.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Using Poetry (Recommended)](#using-poetry-recommended)
  - [Using pip](#using-pip)
- [Project Structure](#project-structure)
- [Usage](#usage)
  - [Basic Commands](#basic-commands)
  - [Examples](#examples)
  - [Configuration](#configuration)
- [Development](#development)
  - [Setup](#setup)
  - [Running Tests](#running-tests)
  - [Code Quality](#code-quality)
  - [Versioning](#versioning)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Features

- ✅ Validate gateway selector rulesets
- 📋 List available gateways
- 🚀 Simple and intuitive CLI interface
- 🧪 Comprehensive test suite
- 🔧 Configurable through environment variables

## Prerequisites

- Python 3.9 or higher
- [Poetry](https://python-poetry.org/) (recommended) or pip
- Git (for development)

## Installation

### Using Poetry (Recommended)

1. Install Poetry if you haven't already:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Clone the repository (if not already cloned):
   ```bash
   git clone https://your-repository-url.git
   cd my_monorepo/packages/kp_gs_cli
   ```

3. Install the package and its dependencies:
   ```bash
   poetry install
   ```

### Using pip

```bash
# Navigate to the project directory
cd my_monorepo/packages/kp_gs_cli

# Install the package in development mode
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

## Project Structure

```
kp_gs_cli/
├── kp_gs_cli/           # Main package
│   ├── __init__.py      # Package initialization
│   └── main.py          # CLI entry point
├── tests/               # Test files
├── pyproject.toml       # Project configuration
└── README.md            # This file
```

## Usage

### Basic Commands

```bash
# Show help
poetry run kp-gs --help

# Show version
poetry run kp-gs version

# Validate a ruleset file
poetry run kp-gs validate path/to/ruleset.json

# List available gateways
poetry run kp-gs list-gateways
```

### Examples

```bash
# Validate a ruleset with verbose output
poetry run kp-gs validate --verbose path/to/ruleset.json

# List gateways in JSON format
poetry run kp-gs list-gateways --format json
```

### Configuration

The CLI can be configured using environment variables:

- `KP_GS_LOG_LEVEL`: Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `KP_GS_CONFIG_PATH`: Path to a custom configuration file

## Development

### Setup

1. Fork and clone the repository
2. Install development dependencies:
   ```bash
   poetry install --with dev
   ```
3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=kp_gs_cli --cov-report=term-missing

# Run a specific test file
pytest tests/test_main.py
```

### Code Quality

```bash
# Format code
black .

# Sort imports
isort .

# Check for type errors
mypy kp_gs_cli

# Lint the code
flake8 kp_gs_cli
```

### Versioning

This project uses [Semantic Versioning](https://semver.org/).

## Troubleshooting

### Common Issues

1. **Dependency conflicts**
   - Try removing the virtual environment and reinstalling:
     ```bash
     poetry env remove python
     poetry install
     ```

2. **Command not found**
   - Ensure the package is installed in development mode
   - Check that your `PATH` includes Poetry's bin directory

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Proprietary - KP Team
