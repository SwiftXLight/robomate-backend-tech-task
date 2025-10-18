#!/usr/bin/env python3
"""
CLI script to import events from CSV file.

Usage:
    python -m scripts.import_events data/events_sample.csv
    poetry run import_events data/events_sample.csv
"""

import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

import typer
from rich.console import Console
from rich.progress import track

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.database import get_db_session
from app.services.event_service import EventService
from app.models.event import EventCreate

# Configure logging
configure_logging()
logger = get_logger(__name__)

app = typer.Typer()
console = Console()


def parse_csv_row(row: dict) -> EventCreate:
    """
    Parse CSV row into EventCreate model.
    
    Expected CSV columns:
    - event_id: UUID string
    - occurred_at: ISO-8601 datetime string
    - user_id: string
    - event_type: string
    - properties_json: JSON string (optional)
    """
    # Parse properties JSON
    properties = {}
    if "properties_json" in row and row["properties_json"]:
        try:
            properties = json.loads(row["properties_json"])
        except json.JSONDecodeError:
            logger.warning("Failed to parse properties JSON", event_id=row.get("event_id"))
    
    # Parse datetime
    occurred_at = datetime.fromisoformat(row["occurred_at"].replace("Z", "+00:00"))
    
    return EventCreate(
        event_id=UUID(row["event_id"]),
        user_id=row["user_id"],
        event_type=row["event_type"],
        occurred_at=occurred_at,
        properties=properties,
    )


async def import_events_from_csv(file_path: Path, batch_size: int = 100) -> tuple[int, int, int]:
    """
    Import events from CSV file.
    
    Args:
        file_path: Path to CSV file
        batch_size: Number of events to insert at once
    
    Returns:
        Tuple of (total_imported, total_duplicates, total_failed)
    """
    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        sys.exit(1)
    
    console.print(f"[blue]Reading CSV file: {file_path}[/blue]")
    
    total_imported = 0
    total_duplicates = 0
    total_failed = 0
    batch = []
    
    async with get_db_session() as session:
        event_service = EventService(session)
        
        with open(file_path, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Count total rows for progress bar
            rows = list(reader)
            total_rows = len(rows)
            
            console.print(f"[blue]Found {total_rows} events to import[/blue]")
            
            for row in track(rows, description="Importing events..."):
                try:
                    event = parse_csv_row(row)
                    batch.append(event)
                    
                    # Insert batch when size reached
                    if len(batch) >= batch_size:
                        inserted, duplicates = await event_service.insert_events(batch)
                        total_imported += inserted
                        total_duplicates += duplicates
                        batch = []
                        
                except Exception as e:
                    logger.error("Failed to parse event", error=str(e), row=row)
                    total_failed += 1
            
            # Insert remaining events
            if batch:
                try:
                    inserted, duplicates = await event_service.insert_events(batch)
                    total_imported += inserted
                    total_duplicates += duplicates
                except Exception as e:
                    logger.error("Failed to insert final batch", error=str(e))
                    total_failed += len(batch)
    
    return total_imported, total_duplicates, total_failed


@app.command()
def main(
    csv_path: str = typer.Argument(..., help="Path to CSV file"),
    batch_size: int = typer.Option(100, help="Batch size for inserts"),
) -> None:
    """
    Import events from CSV file into the database.
    
    CSV format:
    - event_id (UUID)
    - occurred_at (ISO-8601 datetime)
    - user_id (string)
    - event_type (string)
    - properties_json (JSON string, optional)
    """
    console.print("[bold green]Event Import Tool[/bold green]")
    console.print(f"Database: {settings.database_url.split('@')[-1]}")
    console.print()
    
    file_path = Path(csv_path)
    
    try:
        # Run async import
        imported, duplicates, failed = asyncio.run(
            import_events_from_csv(file_path, batch_size)
        )
        
        # Print summary
        console.print()
        console.print("[bold green]Import Complete![/bold green]")
        console.print(f"✓ Imported:   {imported:,}")
        console.print(f"⊘ Duplicates: {duplicates:,}")
        console.print(f"✗ Failed:     {failed:,}")
        console.print(f"━ Total:      {imported + duplicates + failed:,}")
        
        if failed > 0:
            console.print("[yellow]Warning: Some events failed to import. Check logs.[/yellow]")
            sys.exit(1)
            
    except KeyboardInterrupt:
        console.print("[yellow]Import cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Import failed: {e}[/red]")
        logger.error("Import failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    app()

