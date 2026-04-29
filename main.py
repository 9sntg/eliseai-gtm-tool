"""CLI entry point for the EliseAI GTM Lead Enrichment Tool."""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime
import logging
import time
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from gtm.models.lead import RawLead
from gtm.pipeline.runner import run_pipeline

DATA_DIR = Path("data")
LEADS_FILE = DATA_DIR / "leads_input.csv"
OUTPUTS_DIR = Path("outputs")
SCHEDULE_FORMAT: str = "%H:%M"

console = Console()
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s — %(message)s")


def load_leads(path: Path) -> list[RawLead]:
    """Read RawLead objects from a CSV file, skipping malformed rows."""
    if not path.exists():
        console.print(f"[red]No leads file found at {path}[/red]")
        return []
    leads: list[RawLead] = []
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            try:
                leads.append(RawLead(**row))
            except Exception as exc:
                console.print(f"[yellow]Skipping malformed row: {exc}[/yellow]")
    return leads


def _render_summary(results: list[RawLead]) -> None:
    """Print a Rich table with one row per processed lead."""
    if not results:
        console.print("[dim]No new leads processed.[/dim]")
        return
    table = Table(title="Pipeline Summary", show_header=True, header_style="bold magenta")
    table.add_column("Company", style="cyan")
    table.add_column("City / State")
    table.add_column("Score", justify="right")
    table.add_column("Tier")
    table.add_column("Email?")
    for r in results:
        table.add_row(
            r.raw.company,
            f"{r.raw.city}, {r.raw.state}",
            f"{r.score:.0f}" if r.score is not None else "—",
            r.tier or "—",
            "yes" if r.email_draft else "no",
        )
    console.print(table)


def run_once() -> None:
    """Load leads from CSV, run the pipeline, and print the summary table."""
    leads = load_leads(LEADS_FILE)
    if not leads:
        return
    console.print(f"[bold]Found {len(leads)} lead(s)[/bold] in {LEADS_FILE}")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running enrichment pipeline…", total=None)
        results = asyncio.run(run_pipeline(leads, OUTPUTS_DIR))
        progress.update(task, description=f"Done — {len(results)} new lead(s) enriched")
    _render_summary(results)


def _seconds_until(hour: int, minute: int, _now: datetime.datetime | None = None) -> float:
    """Return seconds from now until the next occurrence of HH:MM today or tomorrow."""
    now = _now or datetime.datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()


def _schedule_loop(time_str: str) -> None:
    """Run pipeline immediately, then repeat daily at the specified HH:MM time."""
    try:
        parsed = datetime.datetime.strptime(time_str, SCHEDULE_FORMAT)
    except ValueError:
        console.print(f"[red]Invalid schedule time '{time_str}'. Use HH:MM format (e.g. 09:00).[/red]")
        return
    hour, minute = parsed.hour, parsed.minute
    console.print(f"[bold green]Scheduler started. Running daily at {time_str}. Ctrl+C to stop.[/bold green]")
    run_once()
    try:
        while True:
            secs = _seconds_until(hour, minute)
            console.print(f"[dim]Next run in {secs / 3600:.1f}h (at {time_str}).[/dim]")
            time.sleep(secs)
            run_once()
    except KeyboardInterrupt:
        console.print("[dim]Scheduler stopped.[/dim]")


def _watch_loop() -> None:
    """Re-run the pipeline whenever leads_input.csv changes."""
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    class _CsvHandler(FileSystemEventHandler):
        def on_modified(self, event: object) -> None:
            from watchdog.events import FileModifiedEvent
            if isinstance(event, FileModifiedEvent) and Path(event.src_path).resolve() == LEADS_FILE.resolve():
                console.print("[bold blue]CSV updated — re-running pipeline…[/bold blue]")
                run_once()

    observer = Observer()
    observer.schedule(_CsvHandler(), str(DATA_DIR), recursive=False)
    observer.start()
    console.print(f"[bold green]Watching {LEADS_FILE} for changes. Ctrl+C to stop.[/bold green]")
    run_once()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


def main() -> None:
    """Parse arguments and dispatch to run_once, watch loop, or schedule loop."""
    parser = argparse.ArgumentParser(description="EliseAI GTM Lead Enrichment Tool")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--watch", action="store_true", help="Re-run on CSV changes")
    group.add_argument("--schedule", metavar="HH:MM", help="Run daily at the specified time (e.g. 09:00)")
    args = parser.parse_args()

    if args.watch:
        _watch_loop()
    elif args.schedule:
        _schedule_loop(args.schedule)
    else:
        run_once()


if __name__ == "__main__":
    main()
