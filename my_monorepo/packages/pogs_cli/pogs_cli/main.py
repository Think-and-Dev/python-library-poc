import asyncio
import pathlib
import sys
import json
import os
from typing import Optional

# Add project root to path to allow imports
project_root = pathlib.Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(project_root))

import typer
from rich import print
from rich.console import Console
import csv
from decimal import Decimal
from rich.table import Table

from kp_gateway_selector.gateway_selector.compiler.ruleset_compiler import (
    compile_ruleset,
    CompiledRuleset
)
from kp_gateway_selector.gateway_selector.context import make_ctx
from kp_gateway_selector.gateway_selector.selector import select_gateway
from kp_gateway_selector.utils.validate_memo import formatPixKey
from kp_gateway_selector.postgresql import database as _dbmod
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.orm import sessionmaker as _sessionmaker

# DB URL precedence: CLI --db-url > env DATABASE_URL
def _make_session_local(db_url: str | None):
    if not db_url and not os.getenv("DATABASE_URL"):
        raise ValueError(
            "Database connection string is required. "
            "Please set the DATABASE_URL environment variable or use the --db-url option.\n"
            "Example: DATABASE_URL=postgresql://user:pass@localhost:5432/dbname"
        )
    url = db_url or os.getenv("DATABASE_URL")
    _dbmod.ENGINE = _create_engine(url, echo=False, pool_size=50, max_overflow=100)
    _dbmod.SessionLocal = _sessionmaker(bind=_dbmod.ENGINE)
    return _dbmod.SessionLocal
from kp_gateway_selector.postgresql.gateway_selector.database_repo import DatabaseRepo
from kp_gateway_selector.postgresql.gateway_selector.models import GatewaySelectorGatewayConfig, GatewaySelectorRuleSet, GatewaySelectorRule
from kp_gateway_selector.utils.in_memory_repo import InMemoryRepo


# --- Typer App Initialization ---
app = typer.Typer(
    help="Management and validation scripts for the Gateway Selector.",
    rich_markup_mode="markdown",
)
console = Console()


def _run_csv_processing(snapshot: CompiledRuleset, csv_file: pathlib.Path):
    """Helper function to process a CSV file against a compiled ruleset snapshot."""
    console.print(f"\n[bold]Processing rows from {csv_file.name}...[/bold]")
    results_table = Table(title=f"Gateway Selection Results for {csv_file.name}")
    results_table.add_column("Row #", style="cyan")
    results_table.add_column("Input PIX Key", style="magenta")
    results_table.add_column("Input User ID", style="yellow")
    results_table.add_column("PIX Key Type", style="blue")
    results_table.add_column("Selected Gateway", style="green")
    results_table.add_column("Expected Gateway", style="cyan")
    results_table.add_column("Match", justify="center")
    results_table.add_column("Reason", style="dim")

    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f, delimiter='|')
            for i, row in enumerate(reader):
                console.rule(f"Row {i + 1}")
                try:
                    _, _, pix_key_type = formatPixKey(row['pix_key'])
                    ctx = make_ctx(
                        api_user_id=int(row['api_user_id']),
                        pix_key=row['pix_key'],
                        amount=Decimal(row['amount']),
                        pix_key_type=pix_key_type
                    )
                    gw, decision = select_gateway(ctx, snapshot)
                    selected_gw_name = gw.name if gw else None

                    expected_gw_name = row.get('gateway')
                    match_status = ""

                    if expected_gw_name:
                        if selected_gw_name == expected_gw_name:
                            match_status = "[bold green]✔️[/bold green]"
                        else:
                            match_status = "[bold red]❌[/bold red]"

                    results_table.add_row(
                        str(i + 1),
                        row['pix_key'][:50] + '...' if len(row['pix_key']) > 50 else row['pix_key'],
                        row['api_user_id'],
                        pix_key_type,
                        selected_gw_name or "[red]None[/red]",
                        expected_gw_name or "-",
                        match_status,
                        decision.reason
                    )
                except Exception as e:
                    results_table.add_row(str(i + 1), row.get('pix_key', 'N/A'), "-", "-", "[bold red]ERROR[/bold red]", "-", "-", str(e))

        console.print()
        console.print(results_table)
    except FileNotFoundError:
        print(f"[bold red]❌ Error: CSV file not found at '{csv_file}'[/bold red]")
    except Exception as e:
        print(f"[bold red]❌ An unexpected error occurred during CSV processing: {e}[/bold red]")


# --- Typer Commands ---
@app.command()
def version():
    """Show the current version of the KP Gateway Selector CLI."""
    from pogs_cli import __version__
    console.print(f"KP Gateway Selector CLI v{__version__}", style="bold green")


@app.command(name="list")
def list_rulesets(db_url: Optional[str] = typer.Option(None, "--db-url", help="Database URL override")):
    """
    Lists all rulesets stored in the database with their status.
    """
    console.print("[bold]Listing all Gateway Selector Rulesets...[/bold]")
    db = None
    try:
        SessionLocal = _make_session_local(db_url)
        db = SessionLocal()
        rulesets = db.query(GatewaySelectorRuleSet).order_by(GatewaySelectorRuleSet.id).all()

        if not rulesets:
            console.print("[yellow]No rulesets found in the database.[/yellow]")
            return

        table = Table(title="Gateway Selector Rulesets")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Is Active", justify="center")
        table.add_column("Version", justify="right", style="green")
        table.add_column("Default Gateway", style="yellow")
        table.add_column("Created At", style="dim")

        for rs in rulesets:
            active_str = "[bold green]✔️ Yes[/bold green]" if rs.is_active else "[dim]No[/dim]"
            table.add_row(
                str(rs.id),
                rs.name,
                active_str,
                str(rs.version),
                rs.default_gateway,
                str(rs.created_at.strftime("%Y-%m-%d %H:%M")) if rs.created_at else ""
            )

        console.print(table)

    finally:
        if db:
            db.close()


@app.command()
def validate_ruleset(
    ruleset_id: int = typer.Argument(..., help="The ID of the ruleset to validate."),
    db_url: Optional[str] = typer.Option(None, "--db-url", help="Database URL override"),
):
    """
    Compiles a specific ruleset from the database to check for validation errors.
    """
    console.print(f"Attempting to compile ruleset with ID: {ruleset_id} from the database...")

    db = None
    try:
        SessionLocal = _make_session_local(db_url)
        db = SessionLocal()
        repo = DatabaseRepo(db)

        target_ruleset = db.query(GatewaySelectorRuleSet).filter(GatewaySelectorRuleSet.id == ruleset_id).first()
        if not target_ruleset:
            print(f"[bold red]❌ Error: Ruleset with ID {ruleset_id} not found.[/bold red]")
            raise typer.Exit(code=1)

        async def main():
            try:
                active_status = "[bold green]Active[/bold green]" if target_ruleset.is_active else "[red]Inactive[/red]"
                print(f"  Status: {active_status}")
                snapshot = await compile_ruleset(repo, ruleset_id=ruleset_id, debug=True, log=lambda s: console.print(f"[dim]  - {s}[/dim]"))
                print(f"[bold green]✔️ Success![/bold green]")
                print(f"  Ruleset Name: '{snapshot.name}'")
                print(f"  Version: {snapshot.version}")
                print(f"  Total Rules Compiled: {snapshot.total_rules}")
                print(f"  Default Gateway: '{snapshot.default_gateway}'")
                print(f"  Compilation Time: {snapshot.loaded_at_ms:.2f} ms")
                return snapshot
            except (ValueError, RuntimeError) as e:
                print(f"[bold red]❌ Validation Failed![/bold red]")
                print(f"  [red]Error:[/red] {e}")
                return None

        compiled_snapshot = asyncio.run(main())

        if compiled_snapshot:
            if typer.confirm("\nDo you want to process a CSV file with this validated ruleset?", default=False):
                csv_path_str = typer.prompt("Enter the path to the CSV file")
                csv_path = pathlib.Path(csv_path_str)
                if csv_path.is_file():
                    _run_csv_processing(compiled_snapshot, csv_path)
                else:
                    print(f"[bold red]❌ Error: File not found at '{csv_path}'[/bold red]")

    finally:
        if db:
            db.close()


@app.command(name="validate-local-ruleset")
def validate_local_ruleset(
    json_file: pathlib.Path = typer.Argument(..., help="Path to the local JSON file to validate.", exists=True, file_okay=True, dir_okay=False, readable=True)
):
    """
    Compiles a local ruleset JSON file in-memory to check for validation errors.
    Does NOT interact with the database.
    """
    console.print(f"Attempting to compile local ruleset file: {json_file}...")

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[bold red]Error reading or parsing JSON file: {e}[/bold red]")
        raise typer.Exit(code=1)

    async def main():
        try:
            # Use the InMemoryRepo instead of the DatabaseRepo
            repo = InMemoryRepo(data)
            # We pass a dummy ruleset_id; it's not used by InMemoryRepo but is required by compile_ruleset
            snapshot = await compile_ruleset(repo, ruleset_id=-1, debug=True, log=lambda s: console.print(f"[dim]  - {s}[/dim]"))
            print(f"[bold green]✔️ Success![/bold green]")
            print(f"  Ruleset Name: '{snapshot.name}'")
            print(f"  Version: {snapshot.version}")
            print(f"  Total Rules Compiled: {snapshot.total_rules}")
            print(f"  Default Gateway: '{snapshot.default_gateway}'")
            print(f"  Compilation Time: {snapshot.loaded_at_ms:.2f} ms")
            return snapshot
        except (ValueError, RuntimeError) as e:
            print(f"[bold red]❌ Validation Failed![/bold red]")
            print(f"  [red]Error:[/red] {e}")
            return None

    compiled_snapshot = asyncio.run(main())

    if compiled_snapshot:
        if typer.confirm("\nDo you want to process a CSV file with this validated ruleset?", default=False):
            csv_path_str = typer.prompt("Enter the path to the CSV file")
            csv_path = pathlib.Path(csv_path_str)
            if csv_path.is_file():
                _run_csv_processing(compiled_snapshot, csv_path)
            else:
                print(f"[bold red]❌ Error: File not found at '{csv_path}'[/bold red]")


@app.command(name="add")
def add_ruleset(
    json_file: pathlib.Path = typer.Argument(..., help="Path to the JSON file containing the ruleset definition.", exists=True, file_okay=True, dir_okay=False, readable=True),
    db_url: Optional[str] = typer.Option(None, "--db-url", help="Database URL override"),
):
    """
    Adds a new ruleset, including gateways and rules, from a JSON definition file.
    """
    console.print(f"[bold]Adding ruleset from {json_file}...[/bold]")

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[bold red]Error reading or parsing JSON file: {e}[/bold red]")
        raise typer.Exit(code=1)

    db = None
    try:
        SessionLocal = _make_session_local(db_url)
        db = SessionLocal()

        # 1. Pre-process gateways to find new vs. existing
        console.print("Checking gateways...")
        gateways_to_create = []
        found_duplicates = False
        for gw_data in data.get("gateways", []):
            gateway_id = gw_data.get("id")
            gateway_name = gw_data.get("name")

            if not gateway_id or not gateway_name:
                console.print(f"  - [yellow]Skipping gateway because 'id' or 'name' is missing in the JSON.[/yellow]")
                continue

            existing_gateway_by_id = db.query(GatewaySelectorGatewayConfig).filter(GatewaySelectorGatewayConfig.id == gateway_id).first()
            existing_gateway_by_name = db.query(GatewaySelectorGatewayConfig).filter(GatewaySelectorGatewayConfig.name == gateway_name).first()

            if existing_gateway_by_id:
                console.print(f"  - [yellow]Existing[/yellow]: Gateway with ID '{gateway_id}' ('{existing_gateway_by_id.name}') already exists.")
                found_duplicates = True
            elif existing_gateway_by_name:
                console.print(f"  - [yellow]Existing[/yellow]: Gateway with name '{gateway_name}' (ID: {existing_gateway_by_name.id}) already exists.")
                found_duplicates = True
            else:
                console.print(f"  - [green]New[/green]: Gateway '{gateway_name}' (ID: {gateway_id}) will be created.")
                gateways_to_create.append(gw_data)

        # Ask for confirmation if duplicates were found
        if found_duplicates:
            console.print()
            typer.confirm("Some gateways already exist. Do you want to proceed? This will create the ruleset and add only the new gateways (if available).", abort=True)

        # Create the new gateways
        console.print("\nCreating new gateways...")
        if not gateways_to_create:
            console.print("  - No new gateways to create.")
        else:
            for gw_data in gateways_to_create:
                gateway = GatewaySelectorGatewayConfig(**gw_data, updated_by="manage.py")
                db.add(gateway)
                console.print(f"  - Gateway '{gw_data['name']}' (ID: {gw_data['id']}) prepared for creation.")

        # 2. Create Ruleset
        console.print("\nCreating ruleset...")
        ruleset_data = data.get("ruleset")
        if not ruleset_data:
            raise ValueError("JSON file must contain a 'ruleset' object.")

        # Find the currently active ruleset before making changes
        currently_active_ruleset = db.query(GatewaySelectorRuleSet).filter(GatewaySelectorRuleSet.is_active).first()
        activate_new_ruleset = ruleset_data.get("is_active", False)
        # Logic for when the new ruleset will be set to ACTIVE
        if activate_new_ruleset:
            ruleset_data["is_active"] = False

            ruleset = GatewaySelectorRuleSet(**ruleset_data, created_by="manage.py")
            db.add(ruleset)
            db.flush()  # We need to flush to get the new ruleset ID for the rules
            console.print(f"  - Ruleset '{ruleset.name}' prepared with ID: {ruleset.id}")
            console.print(f"  - Default Gateway: '{ruleset_data.get('default_gateway')}'")
            console.print(f"  - [bold green]This new ruleset will be set as ACTIVE[/bold green][bold yellow] after being validated[/bold yellow]")

        # Logic for when the new ruleset will NOT be set to active
        else:
            ruleset = GatewaySelectorRuleSet(**ruleset_data, created_by="manage.py")
            db.add(ruleset)
            db.flush()  # We need to flush to get the new ruleset ID for the rules
            console.print(f"  - Ruleset '{ruleset.name}' prepared with ID: {ruleset.id}")
            console.print(f"  - Default Gateway: '{ruleset_data.get('default_gateway')}'")
            if currently_active_ruleset:
                console.print(f"  - Active ruleset remains: '{currently_active_ruleset.name}' (ID: {currently_active_ruleset.id})")
            else:
                console.print("  - [yellow]Warning: No ruleset is currently active.[/yellow]")

        # 3. Create Rules
        console.print("\nCreating rules...")
        for rule_data in data.get("rules", []):
            rule = GatewaySelectorRule(rule_set_id=ruleset.id, **rule_data, created_by="manage.py")
            db.add(rule)
            console.print(f"  - Rule '{rule_data['name']}' prepared.")

        typer.confirm("\nAre you sure you want to commit these changes to the database?", abort=True)

        db.commit()
        if activate_new_ruleset:
            # validate the new ruleset
            console.print(f"  - Validating new ruleset: '{ruleset.name}' (ID: {ruleset.id})")
            try:
                async def validate():
                    repo = DatabaseRepo(db)
                    return await compile_ruleset(repo, ruleset_id=ruleset.id)
                snapshot = asyncio.run(validate())
                print(f"[bold green]✔️ Validation successful.[/bold green] ({snapshot.total_rules} rules compiled in {snapshot.loaded_at_ms:.2f} ms)")
            except (ValueError, RuntimeError) as e:
                print(f"[bold red]❌ Validation Failed! Cannot activate a broken ruleset.[/bold red]")
                print(f"  [red]Error:[/red] {e}")
                raise typer.Exit(code=1)

            # deactivate the current active ruleset
            if currently_active_ruleset:
                console.print(f"  - Deactivating current active ruleset: '{currently_active_ruleset.name}' (ID: {currently_active_ruleset.id})")
                currently_active_ruleset.is_active = False
                db.add(currently_active_ruleset)
            console.print(f"  - Activating new ruleset: '{ruleset.name}' (ID: {ruleset.id})")
            ruleset.is_active = True
            db.add(ruleset)
            db.commit()
        print("\n[bold green]✔️ Success![/bold green] Ruleset and all associated objects have been committed to the database.")

    except typer.Abort:
        if db:
            db.rollback()
        print("\n[bold yellow]Operation cancelled by user. All changes have been rolled back.[/bold yellow]")

    except (ValueError, KeyError, Exception) as e:
        print(f"[bold red]❌ Operation Failed! {e}[/bold red]")
        if db:
            db.rollback()
        raise typer.Exit(code=1)
    finally:
        if db:
            db.close()


@app.command(name="delete")
def delete_ruleset(
    ruleset_id: int = typer.Argument(..., help="The ID of the ruleset to delete."),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation."),
    db_url: Optional[str] = typer.Option(None, "--db-url", help="Database URL override"),
):
    """
    Deletes a ruleset and all of its associated rules from the database.
    """
    console.print(f"[bold]Attempting to delete ruleset with ID: {ruleset_id}...[/bold]")
    db = None
    try:
        SessionLocal = _make_session_local(db_url)
        db = SessionLocal()
        ruleset = db.query(GatewaySelectorRuleSet).filter(GatewaySelectorRuleSet.id == ruleset_id).first()

        if not ruleset:
            print(f"[bold red]❌ Error: Ruleset with ID {ruleset_id} not found.[/bold red]")
            raise typer.Exit(code=1)

        if ruleset.is_active:
            print("[bold red]❌ Error: Cannot delete an active ruleset. Please activate another ruleset first.[/bold red]")
            raise typer.Exit(code=1)

        rules_to_delete = db.query(GatewaySelectorRule).filter(GatewaySelectorRule.rule_set_id == ruleset_id).all()

        console.print(f"Found ruleset: [magenta]'{ruleset.name}'[/magenta] (ID: {ruleset.id}) with {len(rules_to_delete)} associated rule(s).")

        if not force:
            typer.confirm("Are you sure you want to delete this ruleset and all its rules? This action cannot be undone.", abort=True)

        console.print("Deleting rules...")
        for rule in rules_to_delete:
            db.delete(rule)

        console.print("Deleting ruleset...")
        db.delete(ruleset)

        db.commit()
        print("[bold green]✔️ Success![/bold green] The ruleset and its rules have been deleted.")

    except typer.Abort:
        print("\n[bold yellow]Delete operation cancelled.[/bold yellow]")
    except Exception as e:
        print(f"[bold red]❌ Operation Failed! {e}[/bold red]")
        if db:
            db.rollback()
        raise typer.Exit(code=1)
    finally:
        if db:
            db.close()


@app.command(name="export")
def export_ruleset(
    ruleset_id: int = typer.Argument(..., help="The ID of the ruleset to export."),
    output_file: Optional[pathlib.Path] = typer.Argument(None, help="Optional path to save the exported JSON file. If not provided, prints to console."),
    db_url: Optional[str] = typer.Option(None, "--db-url", help="Database URL override"),
):
    """
    Exports a ruleset and its rules to a JSON format.
    """
    console.print(f"[bold]Exporting ruleset with ID: {ruleset_id}...[/bold]")
    db = None
    try:
        SessionLocal = _make_session_local(db_url)
        db = SessionLocal()
        ruleset = db.query(GatewaySelectorRuleSet).filter(GatewaySelectorRuleSet.id == ruleset_id).first()

        if not ruleset:
            print(f"[bold red]❌ Error: Ruleset with ID {ruleset_id} not found.[/bold red]")
            raise typer.Exit(code=1)

        rules = db.query(GatewaySelectorRule).filter(GatewaySelectorRule.rule_set_id == ruleset_id).order_by(GatewaySelectorRule.priority).all()

        # Build the exportable data structure
        ruleset_data = {
            "name": ruleset.name,
            "is_active": ruleset.is_active,
            "version": ruleset.version,
            "default_gateway": ruleset.default_gateway,
            "sticky_salt": ruleset.sticky_salt,
        }

        rules_data = []
        for rule in rules:
            rules_data.append({
                "priority": rule.priority,
                "name": rule.name,
                "enabled": rule.enabled,
                "condition_type": rule.condition_type,
                "condition_value": rule.condition_value,
                "condition_json": rule.condition_json,
                "action": rule.action,
            })

        export_data = {
            "ruleset": ruleset_data,
            "rules": rules_data,
        }

        json_output = json.dumps(export_data, indent=2)

        if output_file:
            if output_file.exists():
                typer.confirm(f'File "{output_file}" already exists. Overwrite?', abort=True)

            output_file.write_text(json_output)
            print(f"[bold green]✔️ Success![/bold green] Ruleset exported to {output_file}.")
        else:
            # Print to console
            print(json_output)

    except typer.Abort:
        print("\n[bold yellow]Export operation cancelled.[/bold yellow]")
    except Exception as e:
        print(f"[bold red]❌ Operation Failed! {e}[/bold red]")
        if db:
            db.rollback()
        raise typer.Exit(code=1)
    finally:
        if db:
            db.close()


@app.command(name="activate")
def activate_ruleset(
    ruleset_id: int = typer.Argument(..., help="The ID of the ruleset to activate."),
    force: bool = typer.Option(False, "--force", "-f", help="Force activation without confirmation."),
    db_url: Optional[str] = typer.Option(None, "--db-url", help="Database URL override"),
):
    """
    Activates a ruleset after validating it. Deactivates any other active ruleset.
    """
    console.print(f"[bold]Attempting to activate ruleset with ID: {ruleset_id}...[/bold]")
    db = None
    try:
        SessionLocal = _make_session_local(db_url)
        db = SessionLocal()
        repo = DatabaseRepo(db)

        # 1. Validate the ruleset first
        console.print("Step 1: Validating target ruleset...")
        try:
            async def validate():
                return await compile_ruleset(repo, ruleset_id=ruleset_id)
            snapshot = asyncio.run(validate())
            print(f"[bold green]✔️ Validation successful.[/bold green] ({snapshot.total_rules} rules compiled in {snapshot.loaded_at_ms:.2f} ms)")
        except (ValueError, RuntimeError) as e:
            print(f"[bold red]❌ Validation Failed! Cannot activate a broken ruleset.[/bold red]")
            print(f"  [red]Error:[/red] {e}")
            raise typer.Exit(code=1)

        # 2. Get target and current active rulesets
        target_ruleset = db.query(GatewaySelectorRuleSet).filter(GatewaySelectorRuleSet.id == ruleset_id).first()
        if not target_ruleset: # Should be caught by validation, but as a safeguard
            print(f"[bold red]❌ Error: Ruleset with ID {ruleset_id} not found.[/bold red]")
            raise typer.Exit(code=1)

        if target_ruleset.is_active:
            print(f"[bold yellow]✔️ Ruleset '{target_ruleset.name}' (ID: {target_ruleset.id}) is already active.[/bold yellow]")
            return

        active_ruleset = db.query(GatewaySelectorRuleSet).filter(GatewaySelectorRuleSet.is_active).first()

        # 3. Confirm with the user
        console.print("\nStep 2: Review changes")
        if active_ruleset:
            print(f"  - [bold red]DEACTIVATE[/bold red]: '{active_ruleset.name}' (ID: {active_ruleset.id}) ")
        print(f"  - [bold green]ACTIVATE[/bold green]  : '{target_ruleset.name}' (ID: {target_ruleset.id})")

        if not force:
            print()
            typer.confirm("Are you sure you want to proceed with this change?", abort=True)

        # 4. Apply changes
        console.print("\nStep 3: Applying changes...")
        if active_ruleset:
            active_ruleset.is_active = False
            db.add(active_ruleset)

        target_ruleset.is_active = True
        db.add(target_ruleset)

        db.commit()
        print("\n[bold green]✔️ Success![/bold green] Ruleset has been activated.")

    except typer.Abort:
        print("\n[bold yellow]Activation cancelled.[/bold yellow]")
    except Exception as e:
        print(f"[bold red]❌ Operation Failed! {e}[/bold red]")
        if db:
            db.rollback()
        raise typer.Exit(code=1)
    finally:
        if db:
            db.close()


@app.command(name="process-csv")
def process_csv(
    csv_file: pathlib.Path = typer.Argument(..., help="Path to the CSV file to process.", exists=True, file_okay=True, dir_okay=False, readable=True),
    ruleset_id: Optional[int] = typer.Option(None, "--ruleset-id", "-id", help="The ID of the ruleset to use. If not provided, the active ruleset will be used."),
    db_url: Optional[str] = typer.Option(None, "--db-url", help="Database URL override"),
):
    """
    Processes a CSV file to simulate gateway selection for each row against a given ruleset.
    """
    console.print(f"[bold]Processing CSV file: {csv_file}[/bold]")
    db = None
    try:
        SessionLocal = _make_session_local(db_url)
        db = SessionLocal()
        repo = DatabaseRepo(db)

        # 1. Compile the ruleset
        ruleset_str = f"ruleset with ID {ruleset_id}" if ruleset_id else "active ruleset"
        console.print(f"Step 1: Compiling {ruleset_str} with debug mode...")
        try:
            async def do_compile():
                return await compile_ruleset(repo, ruleset_id=ruleset_id, debug=True, log=lambda s: console.print(f"[dim]  - {s}[/dim]"))
            snapshot = asyncio.run(do_compile())
            print(f"[bold green]✔️ Compilation successful.[/bold green]")
        except (ValueError, RuntimeError) as e:
            print(f"[bold red]❌ Compilation Failed![/bold red]")
            print(f"  [red]Error:[/red] {e}")
            raise typer.Exit(code=1)

        # 2. Process CSV
        _run_csv_processing(snapshot, csv_file)

    except Exception as e:
        print(f"[bold red]❌ An unexpected error occurred: {e}[/bold red]")
        if db:
            db.rollback()
        raise typer.Exit(code=1)
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    app()
