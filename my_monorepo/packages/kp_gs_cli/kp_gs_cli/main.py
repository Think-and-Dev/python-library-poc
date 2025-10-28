"""
KP Gateway Selector CLI entry point.

This module provides the main entry point for the KP Gateway Selector CLI.
"""

import sys
import typer
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.table import Table

# Try to import kp_gateway_selector, but make it optional
try:
    from kp_gateway_selector import __version__ as gs_version
    HAS_GS = True
except ImportError:
    HAS_GS = False

# Initialize the CLI app
app = typer.Typer(
    name="kp-gs",
    help="CLI tool for managing and validating KP Gateway Selector rulesets",
    add_completion=False,
)

# Global console instance for rich output
console = Console()

# Add subcommands from other modules
# from kp_gs_cli.commands import validate, list_gateways, ...

@app.command()
def version():
    """Show the current version of the KP Gateway Selector CLI."""
    from kp_gs_cli import __version__
    console.print(f"KP Gateway Selector CLI v{__version__}", style="bold green")

@app.command()
def validate(
    file_path: str = typer.Argument(
        ...,
        help="Path to the ruleset file to validate",
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
    )
):
    """Validate a ruleset file."""
    console.print(f"Validating ruleset file: {file_path}", style="bold blue")
    
    if not HAS_GS:
        console.print(
            "⚠️  kp-gateway-selector is not installed. Only basic file validation will be performed.",
            style="bold yellow"
        )
        console.print("   To enable full validation, install with: poetry install --extras local", style="yellow")
    
    try:
        with open(file_path, 'r') as f:
            # Basic validation - file is readable
            content = f.read()
            
        if HAS_GS:
            # TODO: Implement actual validation logic using kp_gateway_selector
            # Example:
            # from kp_gateway_selector.validator import validate_ruleset
            # validate_ruleset(content)
            pass
            
        console.print("✅ Basic validation passed!", style="bold green")
        if not HAS_GS:
            console.print("   Note: Full validation requires kp-gateway-selector", style="dim")
            
    except Exception as e:
        console.print(f"❌ Validation failed: {str(e)}", style="bold red")
        raise typer.Exit(code=1)

@app.command()
def list_gateways():
    """List all available gateways."""
    # TODO: Implement actual gateway listing using kp_gateway_selector
    # This is a placeholder implementation
    gateways = [
        {"id": "stripe", "name": "Stripe", "status": "active"},
        {"id": "paypal", "name": "PayPal", "status": "active"},
        {"id": "adyen", "name": "Adyen", "status": "inactive"},
    ]
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Status")
    
    for gateway in gateways:
        status_style = "green" if gateway["status"] == "active" else "red"
        table.add_row(
            gateway["id"],
            gateway["name"],
            f"[{status_style}]{gateway['status']}",
        )
    
    console.print("\nAvailable Gateways:")
    console.print(table)

# This allows the package to be run as `python -m kp_gs_cli`
if __name__ == "__main__":
    app()
