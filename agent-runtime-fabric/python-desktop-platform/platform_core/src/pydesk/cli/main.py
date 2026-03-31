from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer
from rich import print

from pydesk.core.config import load_config

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
    validate()
    entry = Path("desktop/main.py")
    subprocess.run(["python", str(entry), "--dev"], check=True)


@app.command()
def build() -> None:
    """Build a distributable app binary (stub for V2-ready baseline)."""
    validate()
    entry = Path("desktop/main.py")

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
def validate() -> None:
    """Validate manifest/config conventions and fail early with actionable errors."""
    platform_toml = Path("platform.toml")
    if not platform_toml.exists():
        raise typer.BadParameter("Missing platform.toml in current project.")

    cfg = load_config(Path.cwd())
    if cfg.width < 400 or cfg.height < 300:
        raise typer.BadParameter("desktop.width/height are too small; minimum is 400x300.")

    print(f"[green]Manifest OK[/green] {cfg.name} ({cfg.version})")


@app.command("add-plugin")
def add_plugin(name: str) -> None:
    """Scaffold a plugin file in plugins/<name>.py."""
    plugin_dir = Path("plugins")
    plugin_dir.mkdir(exist_ok=True)
    plugin_path = plugin_dir / f"{name}.py"

    if plugin_path.exists():
        raise typer.BadParameter(f"Plugin '{name}' already exists at {plugin_path}.")

    scaffold = f'''from __future__ import annotations


class SamplePlugin:
    name = "{name}"

    def register(self, bridge: object) -> None:
        # Attach capabilities to bridge at startup.
        setattr(bridge, "plugin_{name}", lambda: {{"status": "ok", "plugin": "{name}"}})


PLUGIN = SamplePlugin()
'''
    plugin_path.write_text(scaffold, encoding="utf-8")
    print(f"[green]Created[/green] plugin scaffold: {plugin_path}")


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
