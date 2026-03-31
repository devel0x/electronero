from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import typer
from rich import print

from pydesk.core.config import ConfigError, load_config

app = typer.Typer(help="PyDesk CLI - scaffold, develop, and package Python desktop apps.")


def _ensure_desktop_entrypoint() -> Path:
    entry = Path("desktop/main.py")
    if not entry.exists():
        raise typer.BadParameter("Missing desktop/main.py in current project.")
    return entry


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
    entry = _ensure_desktop_entrypoint()
    subprocess.run(["python", str(entry), "--dev"], check=True)


@app.command()
def build() -> None:
    """Build a distributable app binary (PyInstaller baseline)."""
    validate()
    entry = _ensure_desktop_entrypoint()

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
def validate(json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output.")) -> None:
    """Validate manifest/config conventions and fail early with actionable errors."""
    platform_toml = Path("platform.toml")
    errors: list[str] = []

    if not platform_toml.exists():
        errors.append("Missing platform.toml in current project.")
    if not Path("desktop/main.py").exists():
        errors.append("Missing desktop/main.py")

    cfg = None
    if not errors:
        try:
            cfg = load_config(Path.cwd())
        except (ConfigError, ValueError) as exc:
            errors.append(str(exc))

    if cfg is not None:
        for relative_root in cfg.filesystem_roots:
            root = (Path.cwd() / relative_root).resolve()
            if not str(root).startswith(str(Path.cwd().resolve())):
                errors.append(f"filesystem root escapes project: {relative_root}")

    if json_output:
        payload = {"ok": not errors, "errors": errors}
        print(json.dumps(payload))
        if errors:
            raise typer.Exit(code=1)
        return

    if errors:
        for err in errors:
            print(f"[red]Validation error:[/red] {err}")
        raise typer.Exit(code=1)

    if cfg is not None:
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
def doctor(json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output.")) -> None:
    """Check local toolchain prerequisites."""
    checks = {
        "python": shutil.which("python"),
        "pyinstaller": shutil.which("pyinstaller"),
    }

    if json_output:
        payload = {k: bool(v) for k, v in checks.items()}
        print(json.dumps(payload))
        return

    for tool, location in checks.items():
        status = "OK" if location else "MISSING"
        color = "green" if location else "red"
        print(f"[{color}]{tool:12} {status}[/{color}] {location or ''}")


if __name__ == "__main__":
    app()
