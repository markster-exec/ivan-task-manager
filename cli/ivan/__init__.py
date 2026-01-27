#!/usr/bin/env python3
"""Ivan Task Manager CLI.

Usage:
    ivan next      - Show highest priority task
    ivan done      - Mark current task complete, show next
    ivan skip      - Skip current task, show next
    ivan tasks     - List all tasks sorted by priority
    ivan morning   - Show morning briefing
    ivan sync      - Force sync from all sources
    ivan blocking  - Show who's waiting on you
    ivan blocked   - Show what you're waiting on
"""

import os
import sys
from typing import Optional

import click
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

# API base URL (Railway in production, localhost in dev)
API_BASE = os.getenv("IVAN_API_URL", "http://localhost:8000")

console = Console()


def _handle_api_error(error: Exception, endpoint: str) -> None:
    """Handle API errors with user-friendly messages."""
    if isinstance(error, httpx.ConnectError):
        console.print()
        console.print("[red]⚠️  Cannot connect to Ivan Task Manager API[/red]")
        console.print()
        console.print(f"[dim]Tried: {API_BASE}{endpoint}[/dim]")
        console.print()
        console.print("[dim]Possible causes:[/dim]")
        console.print("[dim]  • API server is not running[/dim]")
        console.print("[dim]  • IVAN_API_URL environment variable is incorrect[/dim]")
        console.print("[dim]  • Network connectivity issues[/dim]")
        console.print()
        console.print(
            "[dim]If using Railway: export IVAN_API_URL=https://your-app.up.railway.app[/dim]"
        )
    elif isinstance(error, httpx.TimeoutException):
        console.print()
        console.print("[red]⚠️  Request timed out[/red]")
        console.print(
            "[dim]The API is taking too long to respond. Try again later.[/dim]"
        )
    elif isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        console.print()
        if status == 400:
            # Try to get error message from response
            try:
                detail = error.response.json().get("detail", "Bad request")
                console.print(f"[red]⚠️  {detail}[/red]")
            except Exception:
                console.print("[red]⚠️  Bad request[/red]")
        elif status == 404:
            console.print(f"[red]⚠️  Endpoint not found: {endpoint}[/red]")
        elif status >= 500:
            console.print("[red]⚠️  Server error - the API is having issues[/red]")
        else:
            console.print(f"[red]⚠️  API Error: HTTP {status}[/red]")
    else:
        console.print()
        console.print(f"[red]⚠️  Unexpected error: {error}[/red]")
    sys.exit(1)


def api_get(endpoint: str) -> dict:
    """Make GET request to API."""
    try:
        response = httpx.get(f"{API_BASE}{endpoint}", timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        _handle_api_error(e, endpoint)


def api_post(endpoint: str, data: Optional[dict] = None) -> dict:
    """Make POST request to API."""
    try:
        response = httpx.post(f"{API_BASE}{endpoint}", json=data or {}, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        _handle_api_error(e, endpoint)


def format_task(task: dict, show_context: bool = True) -> Panel:
    """Format a task as a rich Panel."""
    breakdown = task.get("score_breakdown", {})
    flags = []

    if task.get("is_revenue"):
        flags.append("[green]Revenue[/green]")
    if task.get("is_blocking"):
        flags.append(f"[yellow]Blocking: {', '.join(task['is_blocking'])}[/yellow]")
    flags.append(f"[blue]{breakdown.get('urgency_label', 'Unknown')}[/blue]")

    content = Text()
    content.append(f"Score: {task.get('score', 0)}", style="bold")
    content.append(f" | {' | '.join(flags)}\n\n", style="dim")

    if task.get("description"):
        desc = task["description"][:200]
        if len(task["description"]) > 200:
            desc += "..."
        content.append(f"{desc}\n\n", style="dim")

    content.append(f"🔗 {task.get('url', 'No URL')}", style="cyan underline")

    return Panel(
        content,
        title=f"[bold]{task.get('title', 'Untitled')}[/bold]",
        subtitle=f"[dim]{task.get('source', 'unknown')}:{task.get('id', '?').split(':')[-1]}[/dim]",
        border_style="green" if task.get("is_revenue") else "blue",
    )


@click.group()
def cli():
    """Ivan Task Manager - Your personal task command center."""
    pass


@cli.command()
def next():
    """Show the highest priority task to work on."""
    with console.status("[bold blue]Finding your next task...", spinner="dots"):
        data = api_get("/next")

    if not data.get("task"):
        console.print()
        console.print("[green]✨ No tasks in queue. Enjoy your day![/green]")
        console.print()
        return

    task = data["task"]
    console.print()
    console.print(format_task(task))
    console.print()
    console.print(
        "[dim]When done: [bold]ivan done[/bold] | To skip: [bold]ivan skip[/bold][/dim]"
    )


@cli.command()
def done():
    """Mark current task as complete and show next."""
    with console.status("[bold blue]Marking task complete...", spinner="dots"):
        data = api_post("/done")

    if data.get("success"):
        console.print()
        console.print(f"[green]✓[/green] {data.get('message', 'Task completed')}")

        if data.get("next_task"):
            console.print()
            console.print("[bold]Next up:[/bold]")
            console.print(format_task(data["next_task"]))
        else:
            console.print()
            console.print("[green]✨ All done! No more tasks.[/green]")
        console.print()
    else:
        console.print()
        console.print(f"[red]⚠️  {data.get('message', 'Could not complete task')}[/red]")
        console.print("[dim]Tip: Run [bold]ivan next[/bold] first to get a task.[/dim]")
        console.print()


@cli.command()
def skip():
    """Skip current task and show next one."""
    with console.status("[bold blue]Skipping to next task...", spinner="dots"):
        data = api_post("/skip")

    if data.get("success"):
        console.print()
        console.print(f"[yellow]→[/yellow] {data.get('message', 'Task skipped')}")

        if data.get("next_task"):
            console.print()
            console.print("[bold]Next up:[/bold]")
            console.print(format_task(data["next_task"]))
        else:
            console.print()
            console.print("[dim]No more tasks.[/dim]")
        console.print()
    else:
        console.print()
        console.print(f"[red]⚠️  {data.get('message', 'Could not skip task')}[/red]")
        console.print("[dim]Tip: Run [bold]ivan next[/bold] first to get a task.[/dim]")
        console.print()


@cli.command()
def tasks():
    """List all tasks sorted by priority."""
    data = api_get("/tasks")

    if not data:
        console.print("[dim]No tasks found.[/dim]")
        return

    table = Table(title="All Tasks (sorted by priority)")
    table.add_column("#", style="dim", width=3)
    table.add_column("Score", justify="right", style="cyan", width=6)
    table.add_column("Title", style="bold")
    table.add_column("Due", width=12)
    table.add_column("Flags", width=20)

    for i, task in enumerate(data, 1):
        flags = []
        if task.get("is_revenue"):
            flags.append("💰")
        if task.get("is_blocking"):
            flags.append(f"⏳ {len(task['is_blocking'])}")

        breakdown = task.get("score_breakdown", {})
        urgency = breakdown.get("urgency_label", "")

        due = task.get("due_date", "-")
        if urgency == "Overdue":
            due = f"[red]{due}[/red]"
        elif urgency == "Due today":
            due = f"[yellow]{due}[/yellow]"

        table.add_row(
            str(i),
            str(task.get("score", 0)),
            task.get("title", "Untitled")[:50],
            due,
            " ".join(flags),
        )

    console.print()
    console.print(table)
    console.print()
    console.print(
        f"[dim]Total: {len(data)} tasks | Run [bold]ivan next[/bold] to start working[/dim]"
    )


@cli.command()
def morning():
    """Show morning briefing."""
    data = api_get("/morning")

    console.print()
    console.print("[bold yellow]☀️ Good morning, Ivan[/bold yellow]")
    console.print()

    # Top tasks
    console.print("[bold]🔥 TOP FOCUS[/bold]")
    for i, task in enumerate(data.get("top_tasks", []), 1):
        breakdown = task.get("breakdown", {})
        console.print(f"\n{i}. [bold]{task.get('title', 'Untitled')}[/bold]")
        console.print(
            f"   Score: {task.get('score', 0)} | {breakdown.get('urgency_label', '')}"
        )
        console.print(f"   🔗 {task.get('url', 'No URL')}")

    # Summary
    summary = data.get("summary", {})
    console.print()
    console.print("[bold]📊 SUMMARY[/bold]")
    console.print(f"• {summary.get('overdue', 0)} tasks overdue")
    console.print(f"• {summary.get('due_today', 0)} tasks due today")
    blocking = summary.get("blocking", [])
    console.print(
        f"• {len(blocking)} people waiting on you ({', '.join(blocking) if blocking else 'none'})"
    )

    console.print()
    console.print("[dim]Type [bold]ivan next[/bold] to start working.[/dim]")


@cli.command()
def sync():
    """Force sync from all sources."""
    console.print()

    with console.status(
        "[bold blue]Syncing from ClickUp and GitHub...", spinner="dots"
    ):
        data = api_post("/sync")

    if data.get("success"):
        results = data.get("results", {})
        clickup_count = results.get("clickup", 0)
        github_count = results.get("github", 0)
        errors = results.get("errors", [])

        # Show success counts
        if clickup_count > 0:
            console.print(f"[green]✓[/green] ClickUp: {clickup_count} tasks synced")
        else:
            console.print("[dim]○[/dim] ClickUp: No tasks found")

        if github_count > 0:
            console.print(f"[green]✓[/green] GitHub: {github_count} issues synced")
        else:
            console.print("[dim]○[/dim] GitHub: No issues found")

        # Show errors
        if errors:
            console.print()
            console.print("[bold yellow]⚠️  Some sources had issues:[/bold yellow]")
            for error in errors:
                console.print(f"[yellow]  • {error}[/yellow]")

        # Summary
        total = clickup_count + github_count
        console.print()
        if total > 0:
            console.print(
                f"[dim]Total: {total} tasks synced. Run [bold]ivan tasks[/bold] to see them.[/dim]"
            )
        else:
            console.print(
                "[dim]No tasks synced. Check API tokens in Railway settings.[/dim]"
            )
    else:
        console.print("[red]✗ Sync failed[/red]")
        console.print("[dim]Check the API logs for details.[/dim]")


@cli.command()
def blocking():
    """Show who's waiting on you."""
    data = api_get("/tasks")

    blocking_tasks = [t for t in data if t.get("is_blocking")]

    if not blocking_tasks:
        console.print("[green]✓ Nobody is waiting on you![/green]")
        return

    console.print("[bold yellow]⏳ People waiting on you:[/bold yellow]")
    console.print()

    for task in blocking_tasks:
        people = ", ".join(task.get("is_blocking", []))
        console.print(f"• [bold]{task.get('title')}[/bold]")
        console.print(f"  Blocking: [yellow]{people}[/yellow]")
        console.print(f"  🔗 {task.get('url')}")
        console.print()


@cli.command()
def blocked():
    """Show what you're waiting on."""
    # TODO: Implement blocked_by tracking
    console.print("[dim]Coming soon: Show tasks you're blocked on[/dim]")


if __name__ == "__main__":
    cli()
