#!/usr/bin/env python3
"""Ivan Task Manager CLI.

Usage:
    ivan next                  - Show highest priority task
    ivan done [--comment TEXT] - Mark current task complete, optionally add comment
    ivan skip                  - Skip current task, show next
    ivan comment TEXT          - Add comment to current task
    ivan create TITLE          - Create new task in ClickUp
    ivan tasks                 - List all tasks sorted by priority
    ivan morning               - Show morning briefing
    ivan sync                  - Force sync from all sources
    ivan blocking              - Show who's waiting on you
    ivan blocked               - Show what you're waiting on
    ivan export [--output PATH] - Export tasks to SQLite bundle for offline use
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
    content.append(f" | {' | '.join(flags)}\n", style="dim")

    # Entity context
    if breakdown.get("entity_name"):
        ws_info = ""
        if breakdown.get("workstream_name"):
            ws_info = f" - {breakdown['workstream_name']}"
            if breakdown.get("workstream_deadline"):
                ws_info += f" by {breakdown['workstream_deadline']}"
        content.append(f"-> {breakdown['entity_name']}{ws_info}\n", style="magenta")

    content.append("\n")

    # Show action draft for processor tasks
    action = task.get("action")
    if action and action.get("type") == "github_comment":
        content.append("Draft response:\n", style="bold yellow")
        content.append("+" + "-" * 50 + "+\n", style="dim")
        # Word wrap the draft
        draft = action.get("body", "")
        for line in draft.split("\n"):
            while len(line) > 48:
                content.append(f"| {line[:48]} |\n", style="dim")
                line = line[48:]
            content.append(f"| {line.ljust(48)} |\n", style="dim")
        content.append("+" + "-" * 50 + "+\n", style="dim")
        content.append("\n")
        content.append(
            f"On done: Posts comment to GitHub #{action.get('issue')}\n", style="cyan"
        )
    else:
        # Task URL
        content.append(f"Task: {task.get('url', 'No URL')}", style="cyan underline")

    # Determine border style
    if task.get("source") == "processor":
        border = "yellow"
    elif task.get("is_revenue"):
        border = "green"
    else:
        border = "blue"

    return Panel(
        content,
        title=f"[bold]{task.get('title', 'Untitled')}[/bold]",
        subtitle=f"[dim]{task.get('source', 'unknown')}:{task.get('id', '?').split(':')[-1]}[/dim]",
        border_style=border,
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

    # Show appropriate hints based on task type
    if task.get("source") == "processor":
        console.print(
            "[dim][bold]ivan done[/bold] post as-is | "
            "[bold]ivan done -e[/bold] edit first | "
            "[bold]ivan skip[/bold] next task[/dim]"
        )
    else:
        console.print(
            "[dim]When done: [bold]ivan done[/bold] | To skip: [bold]ivan skip[/bold][/dim]"
        )


@cli.command()
@click.option("--comment", "-c", help="Add a completion comment")
def done(comment: Optional[str]):
    """Mark current task as complete and show next."""
    with console.status("[bold blue]Marking task complete...", spinner="dots"):
        data = api_post("/done")

    if data.get("success"):
        completed_task_id = data.get("completed_task_id")

        # Add comment to the COMPLETED task (not the next one)
        if comment and completed_task_id:
            with console.status("[bold blue]Adding comment...", spinner="dots"):
                api_post(f"/tasks/{completed_task_id}/comment", {"text": comment})

        console.print()
        console.print(f"[green]✓[/green] {data.get('message', 'Task completed')}")
        if comment:
            console.print(f"[dim]Comment added: {comment}[/dim]")

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
@click.argument("text")
def comment(text: str):
    """Add comment to current task."""
    # Get current task ID
    with console.status("[bold blue]Getting current task...", spinner="dots"):
        data = api_get("/next")

    if not data.get("task"):
        console.print()
        console.print("[red]⚠️  No current task to comment on[/red]")
        console.print("[dim]Tip: Run [bold]ivan next[/bold] first to get a task.[/dim]")
        console.print()
        return

    task_id = data["task"]["id"]

    with console.status("[bold blue]Adding comment...", spinner="dots"):
        result = api_post(f"/tasks/{task_id}/comment", {"text": text})

    console.print()
    if result.get("success"):
        console.print(f"[green]✓[/green] Comment added to {data['task']['title'][:40]}...")
    else:
        console.print(f"[red]⚠️  {result.get('message', 'Could not add comment')}[/red]")
    console.print()


@cli.command()
@click.argument("title")
@click.option("--description", "-d", help="Task description")
@click.option("--entity", "-e", help="Entity ID to tag")
@click.option("--source", "-s", default="clickup", help="Source: clickup or github")
def create(title: str, description: Optional[str], entity: Optional[str], source: str):
    """Create new task in source system."""
    with console.status(f"[bold blue]Creating task in {source}...", spinner="dots"):
        result = api_post(
            f"/tasks?source={source}",
            {
                "title": title,
                "description": description,
                "entity_id": entity,
            },
        )

    console.print()
    if result.get("success"):
        console.print(f"[green]✓[/green] {result.get('message', 'Task created')}")
        if result.get("source_id"):
            console.print(f"[dim]ID: {result['source_id']}[/dim]")
    else:
        console.print(f"[red]⚠️  {result.get('message', 'Could not create task')}[/red]")
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


@cli.command()
@click.argument("name")
def entity(name: str):
    """Show entity details and tasks."""
    data = api_get(f"/entities/{name}")

    console.print()
    console.print(f"[bold]{data['name']}[/bold] — {data.get('company') or 'N/A'}")
    if data.get("email"):
        console.print(f"  Email: {data['email']}")
    if data.get("phone"):
        console.print(f"  Phone: {data['phone']}")
    console.print(f"  Type: {data.get('relationship_type') or 'N/A'} | Priority: {data['priority']}")
    console.print()

    if data.get("intention"):
        console.print(f"[bold]Intention:[/bold] {data['intention']}")
        console.print()

    # Workstreams
    if data.get("workstreams"):
        console.print("[bold]Workstreams:[/bold]")
        for ws in data["workstreams"]:
            status_color = {
                "active": "green",
                "blocked": "red",
                "planned": "yellow",
                "complete": "dim",
            }.get(ws["status"], "white")
            deadline = f" — due {ws['deadline']}" if ws.get("deadline") else ""
            revenue = f" ({ws['revenue_potential']})" if ws.get("revenue_potential") else ""
            console.print(f"  [{status_color}][{ws['status']}][/{status_color}] {ws['name']}{deadline}{revenue}")
        console.print()

    # Channels
    if data.get("channels"):
        console.print("[bold]Where to work:[/bold]")
        for key, value in data["channels"].items():
            # Format URLs nicely
            if key == "gdoc":
                url = f"https://docs.google.com/document/d/{value}"
            elif key == "github" and not value.startswith("http"):
                url = f"https://github.com/{value}"
            else:
                url = value
            console.print(f"  {key.capitalize()}: [cyan]{url}[/cyan]")
        console.print()

    # Context
    if data.get("context_summary"):
        console.print("[bold]Context:[/bold]")
        console.print(f"  {data['context_summary'].strip()}")


@cli.command()
def projects():
    """Show all entities grouped by workstream status."""
    data = api_get("/entities")

    if not data:
        console.print("[dim]No entities found.[/dim]")
        return

    console.print()
    console.print("[bold]ACTIVE WORKSTREAMS[/bold]")
    console.print()

    active_found = False
    for entity in sorted(data, key=lambda e: -e["priority"]):
        if entity.get("active_workstream"):
            active_found = True
            console.print(f"[bold]{entity['name']}[/bold] ({entity.get('company') or 'N/A'})")
            console.print(f"  → {entity['active_workstream']}")
            console.print()

    if not active_found:
        console.print("[dim]No active workstreams[/dim]")
        console.print()


@cli.command()
@click.option(
    "--output",
    "-o",
    default="~/Developer/Personal/ivan-os/data/sync",
    help="Output directory for export bundle",
)
def export(output: str):
    """Export tasks to SQLite bundle for ivan-os offline sync."""
    import os

    # Expand ~ in path
    output_path = os.path.expanduser(output)

    with console.status("[bold blue]Exporting tasks...", spinner="dots"):
        result = api_post("/export", {"output_path": output_path, "include_briefs": True})

    console.print()
    if result.get("success"):
        console.print("[green]✓[/green] Export complete")
        console.print(f"  Tasks: {result.get('tasks_count', 0)}")
        console.print(f"  Entities: {result.get('entities_count', 0)}")
        console.print(f"  Output: [cyan]{output_path}[/cyan]")
    else:
        console.print(f"[red]✗[/red] {result.get('message', 'Export failed')}")
    console.print()


@cli.command()
@click.option("--limit", "-l", default=50, help="Max tickets to process")
@click.option("--dry-run", is_flag=True, help="Show what would be processed without creating tasks")
def process(limit: int, dry_run: bool):
    """Process tickets and create actionable tasks."""
    console.print()

    if dry_run:
        console.print("[yellow]DRY RUN - no tasks will be created[/yellow]")
        console.print()

    with console.status("[bold blue]Processing tickets...", spinner="dots"):
        if dry_run:
            # For dry run, just list what would be processed
            data = api_get("/tasks")
            github_tasks = [t for t in data if t.get("source") == "github"]

            console.print(f"[dim]Would process {len(github_tasks[:limit])} GitHub tickets[/dim]")
            return

        result = api_post(f"/process?limit={limit}")

    if result.get("success"):
        console.print(f"[green]✓[/green] {result.get('message', 'Processing complete')}")
        console.print()
        console.print(f"  Processed: {result.get('processed', 0)} tickets")
        console.print(f"  Drafts ready: {result.get('created_tasks', 0)}")
        console.print(f"  Manual tasks: {result.get('manual_tasks', 0)}")
        console.print()

        if result.get("created_tasks", 0) > 0:
            console.print("[dim]Run [bold]ivan next[/bold] to review and approve drafts.[/dim]")
    else:
        console.print(f"[red]✗[/red] {result.get('message', 'Processing failed')}")

    console.print()


@cli.command()
@click.argument("task_number", type=int, required=False)
def context(task_number: int = None):
    """Show entity context for current or specified task."""
    if task_number:
        # Get task by number from list
        tasks = api_get("/tasks")
        if task_number > len(tasks) or task_number < 1:
            console.print(f"[red]Task #{task_number} not found[/red]")
            return
        task = tasks[task_number - 1]
    else:
        # Get current task
        data = api_get("/next")
        if not data.get("task"):
            console.print("[dim]No current task.[/dim]")
            return
        task = data["task"]

    console.print()
    console.print(f"[bold]{task['title']}[/bold]")
    console.print(f"[cyan]{task['url']}[/cyan]")
    console.print()

    # Entity context from score breakdown
    breakdown = task.get("score_breakdown", {})
    if breakdown.get("entity_name"):
        console.print(f"[bold]Entity:[/bold] {breakdown['entity_name']}")
        if breakdown.get("workstream_name"):
            deadline = f" — due {breakdown['workstream_deadline']}" if breakdown.get("workstream_deadline") else ""
            console.print(f"[bold]Workstream:[/bold] {breakdown['workstream_name']}{deadline}")
        console.print()
    else:
        console.print("[dim]No entity context for this task.[/dim]")


if __name__ == "__main__":
    cli()
