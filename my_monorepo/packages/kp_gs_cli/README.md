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
  - [Versioning](#versioning)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Features

- ✅ **Ruleset Management**

  - Create, validate, and manage rulesets
  - Activate/deactivate rulesets with validation
  - Export/import rulesets for backup or migration

- 🔍 **Validation & Testing**

  - Validate rulesets against test cases
  - Process CSV files for batch testing
  - Test rules locally without database access

- 📊 **Database Operations**

  - List all rulesets with status
  - Add new rulesets from JSON definitions
  - Delete rulesets (with safety checks)
  - View detailed ruleset information

- 🛠 **Developer Friendly**
  - Simple and intuitive CLI interface
  - Comprehensive test suite
  - Configurable through environment variables
  - Detailed error messages and logging

## Quick Start

1. First, set up your database connection by exporting the `DATABASE_URL` environment variable:

   ```bash
   export DATABASE_URL="postgresql://username:password@localhost:5432/your_database"
   ```

   Replace the placeholders with your actual database credentials.

2. You can now run any of the CLI commands, for example:

   ```bash
   # List all rulesets
   poetry run kp-gs list
   ```

   Or specify the database URL directly in the command:

   ```bash
   DATABASE_URL="postgresql://username:password@localhost:5432/your_database" poetry run kp-gs list
   ```

## Command Reference

This CLI tool provides commands for managing Gateway Selector V2 rulesets.

### General Syntax

All commands should be run using Poetry:

```bash
poetry run kp-gs [COMMAND] [ARGS]
```

### Available Commands

#### `list`

Lists all rulesets currently stored in the database, along with their status.

**Usage:**

```bash
poetry run kp-gs list
```

#### `validate-ruleset`

Compiles and validates a specific ruleset from the database to check for errors before activation.

After a successful validation, the command will prompt you to optionally process a CSV file. This allows you to immediately test the validated ruleset against a batch of data.

**Interactive Prompt Example:**

```
Do you want to process a CSV file with this validated ruleset? [y/N]: y
Enter the path to the CSV file: resources/gateway_selector_examples_simple.csv
```

**Usage:**

```bash
poetry run kp-gs validate-ruleset <RULESET_ID>
```

**Example:**

```bash
poetry run kp-gs validate-ruleset 7
```

#### `validate-local-ruleset`

Compiles and validates a local ruleset JSON file entirely in-memory, without interacting with the database. This is useful for quick "dry runs" and validating a new or modified ruleset file before adding it to the database.

**Usage:**

```bash
poetry run kp-gs validate-local-ruleset <PATH_TO_JSON_FILE>
```

**Example:**

```bash
poetry run kp-gs validate-local-ruleset resources/sample_ruleset.json
```

#### `add`

Adds a new ruleset, its associated gateways, and rules to the database from a JSON definition file.

**Usage:**

```bash
poetry run kp-gs add <PATH_TO_JSON_FILE>
```

**Example:**

```bash
poetry run kp-gs add resources/sample_ruleset.json
```

#### `export`

Exports a ruleset and its rules from the database to a JSON format. This is useful for backups or for migrating rulesets between environments.

**Usage:**

```bash
poetry run kp-gs export <RULESET_ID> [OUTPUT_FILE_PATH]
```

**Example (print to console):**

```bash
poetry run kp-gs export 33
```

**Example (save to file):**

```bash
poetry run kp-gs export 33 my_ruleset.json
```

#### `delete`

Deletes a ruleset and all of its associated rules from the database. For safety, it will ask for confirmation before deleting. It will not delete an active ruleset.

**Usage:**

```bash
poetry run kp-gs delete <RULESET_ID>
```

**Example:**

```bash
poetry run kp-gs delete 7
```

To skip the confirmation prompt, use the `--force` or `-f` flag.

#### `activate`

Activates a specific ruleset, and deactivates any currently active one. For safety, this command will first validate the target ruleset and ask for confirmation before making any changes.

**Usage:**

```bash
poetry run kp-gs activate <RULESET_ID>
```

**Example:**

```bash
poetry run kp-gs activate 7
```

To skip the confirmation prompt, use the `--force` or `-f` flag.

#### `process-csv`

Processes a CSV file to simulate gateway selection for each row against a given ruleset. This is useful for testing a ruleset against a batch of data.

The CSV file must have `api_user_id`, `amount`, and `pix_key` columns with a `|` delimiter. It can also include an optional `gateway` column containing the expected gateway name for comparison.

**Usage:**

```bash
poetry run kp-gs process-csv <PATH_TO_CSV> [--ruleset-id <RULESET_ID>]
```

**Example (using the active ruleset):**

```bash
poetry run kp-gs process-csv resources/gateway_selector_examples_simple.csv
```

**Example (using a specific ruleset):**

```bash
poetry run kp-gs process-csv resources/gateway_selector_examples_simple.csv --ruleset-id 7
```

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
├── resources/           # Resources files
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
