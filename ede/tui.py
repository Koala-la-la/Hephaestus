"""TUI rendering utilities using Rich.

Provides formatted table rendering for EDE CLI output.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text


console = Console(force_terminal=False, force_interactive=False)


def render_status_dashboard(task: dict, checkpoints: list[dict], audit_logs: list[dict]) -> None:
    """Render a Rich-based dashboard showing project + task status."""

    # ── Task Info Panel ──────────────────────────────
    phase_colors = {
        "spec": "cyan", "design": "blue", "plan": "yellow",
        "code": "green", "test": "magenta", "review": "red", "merge": "white",
    }
    status_colors = {
        "pending": "dim", "running": "yellow", "wait_user": "bold yellow",
        "done": "green", "blocked": "red",
    }

    phase = task.get("phase", "?")
    status = task.get("status", "?")

    info_text = Text()
    info_text.append("Task: ", style="bold")
    info_text.append(task.get("task_id", "?"), style="bold cyan")
    info_text.append(f"\nPhase: ", style="bold")
    info_text.append(phase, style=phase_colors.get(phase, "white"))
    info_text.append(f"\nStatus: ", style="bold")
    info_text.append(status, style=status_colors.get(status, "white"))
    info_text.append(f"\nDescription: {task.get('stage_data', '{}')[:60]}")

    console.print(Panel(info_text, title="[bold]Task Status[/bold]", border_style="cyan"))

    # ── Pipeline Progress ────────────────────────────
    phases = ["spec", "design", "plan", "code", "test", "review", "merge"]
    current_idx = phases.index(phase) if phase in phases else 0

    progress = Text()
    for i, p in enumerate(phases):
        if i < current_idx:
            progress.append(f" {p} ", style="green")
            progress.append("→", style="dim")
        elif i == current_idx:
            progress.append(f" [{p}] ", style=f"bold reverse {phase_colors.get(p, 'white')}")
            progress.append("→", style="dim")
        else:
            progress.append(f" {p} ", style="dim")
            if i < len(phases) - 1:
                progress.append("→", style="dim")

    console.print(Panel(progress, title="[bold]Pipeline[/bold]", border_style="blue"))

    # ── Checkpoint Table ─────────────────────────────
    if checkpoints:
        cpt = Table(title="Checkpoints", show_header=True, header_style="bold")
        cpt.add_column("Stage", style="cyan")
        cpt.add_column("Status", style="yellow")
        cpt.add_column("Confirmed At")
        for cp in checkpoints:
            status = cp.get("status", "?")
            s = {"pending": "⚪ PENDING", "confirmed": "✅ CONFIRMED", "timeout": "⏰ TIMEOUT"}.get(status, status)
            cpt.add_row(cp.get("stage", ""), s, cp.get("confirmed_at", "-"))
        console.print(cpt)

    # ── Audit Log ─────────────────────────────────────
    if audit_logs:
        al = Table(title="Recent Audit Events", show_header=True, header_style="bold")
        al.add_column("Action", style="cyan")
        al.add_column("Detail", style="dim")
        for entry in audit_logs[-5:]:  # last 5
            al.add_row(entry.get("action", ""), (entry.get("detail", "") or "")[:60])
        console.print(al)


def render_init_summary(project_id: str, name: str, db_path: str, ctx_path: str, audit_path: str) -> None:
    """Render project init summary."""
    tbl = Table(title=f"Project '{name}' initialized")
    tbl.add_column("Item", style="cyan")
    tbl.add_column("Path", style="green")
    tbl.add_row("Database", db_path)
    tbl.add_row("Context", ctx_path)
    tbl.add_row("Audit Log", audit_path)
    tbl.add_row("Project ID", project_id)
    console.print(tbl)
    console.print("\n[bold green]OK[/bold green] EDE project ready.")


def render_task_created(task_id: str, description: str) -> None:
    """Render task creation confirmation."""
    console.print(f"[bold green]OK[/bold green] Task [bold]{task_id}[/bold] created: {description}")
    console.print(f"  Phase: spec | Status: pending")
    console.print(f"  Run [bold]ede task run {task_id}[/bold] to start.")


def render_pipeline_result(result: dict) -> None:
    """Render pipeline advance result."""
    if result.get("error"):
        console.print(f"[red]X[/red] {result['error']}")
        return

    state = result.get("state", "unknown")
    phase = result.get("phase", "?")

    if state == "wait_user":
        console.print(f"[bold yellow]!![/bold yellow] Stage [bold]{phase}[/bold] complete — waiting for confirmation.")
        console.print(f"  Run [bold]ede confirm {phase}[/bold] to proceed.")
    elif state == "done":
        console.print(f"[bold green]OK[/bold green] Stage [bold]{phase}[/bold] done.")
    elif state == "terminal":
        console.print(f"[bold green]OK[/bold green] {result.get('message', 'Pipeline complete.')}")
    elif result.get("blocked"):
        console.print(f"[red]X[/red] Blocked by gates: {result.get('failed_gates', [])}")
    else:
        console.print(f"[bold green]OK[/bold green] {result}")


def render_refine_result(suggestions: list, result: dict) -> None:
    """Render self-refinement result."""
    if not suggestions:
        console.print("[dim]No new suggestions.[/dim]")
        return
    console.print(f"Updated: {result['updated']}, Skipped: {result['skipped']}")
