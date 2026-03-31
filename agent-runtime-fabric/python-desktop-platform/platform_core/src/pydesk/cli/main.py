from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer
from rich import print

app = typer.Typer(help="PyDesk CLI - scaffold, develop, and package Python desktop apps.")


@app.command()
def new(name: str, template: str = "blank-app") -> None:
    """Create a new app from a template."""
    source_root = Path(__file__).resolve().parents[1] / "templates" / template
    target_root = Path.cwd() / name

    if not source_root.exists():
        raise typer.BadParameter(f"Template '{template}' was not found.")
    if target_root.exists():
        raise typer.BadParameter(f"Target directory '{target_root}' already exists.")

    shutil.copytree(source_root, target_root)
    print(f"[green]Created[/green] {name} from template '{template}'.")
    print(f"Next: cd {name} && pydesk dev")


@app.command()
def dev() -> None:
    """Run app in development mode from current directory."""
    entry = Path("desktop/main.py")
    if not entry.exists():
        raise typer.BadParameter("Missing desktop/main.py in current project.")
    subprocess.run(["python", str(entry), "--dev"], check=True)


@app.command()
def build() -> None:
    """Build a distributable app binary (stub for V1 vertical slice)."""
    entry = Path("desktop/main.py")
    if not entry.exists():
        raise typer.BadParameter("Missing desktop/main.py in current project.")

    # Kept explicit for transparency and agent friendliness.
    cmd = [
        "pyinstaller",
        "--name",
        Path.cwd().name,
        "--noconfirm",
        "--windowed",
        str(entry),
    ]
    print("[cyan]Running[/cyan] " + " ".join(cmd))
    subprocess.run(cmd, check=True)


@app.command()
def doctor() -> None:
    """Check local toolchain prerequisites."""
    checks = {
        "python": shutil.which("python"),
        "pyinstaller": shutil.which("pyinstaller"),
    }
    for tool, location in checks.items():
        status = "OK" if location else "MISSING"
        color = "green" if location else "red"
        print(f"[{color}]{tool:12} {status}[/{color}] {location or ''}")


if __name__ == "__main__":
    app()
