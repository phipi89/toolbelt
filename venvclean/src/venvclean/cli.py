from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

PRUNED = {
    ".git",
    ".Trash",
    ".cache",
    ".npm",
    ".cargo",
    ".rustup",
    "node_modules",
    "__pycache__",
    "build",
    "dist",
}


def within(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def ignored(path: Path, skips: list[Path]) -> bool:
    return any(within(path, skip) for skip in skips)


def discover(roots: list[Path], skips: list[Path]):
    seen = set()
    for root in roots:

        def onerror(error):
            print(f"Skipping unreadable path: {error.filename}", file=sys.stderr)

        for directory, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
            path = Path(directory)
            if ignored(path, skips):
                dirs[:] = []
                continue
            if "pyvenv.cfg" in files:
                dirs[:] = []  # Never descend into an environment's packages.
                if path not in seen and not path.is_symlink():
                    seen.add(path)
                    yield path
                continue
            dirs[:] = [
                name
                for name in dirs
                if name not in PRUNED
                and not (path / name).is_symlink()
                and not ignored(path / name, skips)
            ]


def configuration(path: Path) -> dict[str, str]:
    values = {}
    for line in (path / "pyvenv.cfg").read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()
    return values


def find_project(environment: Path, roots: list[Path]) -> Path | None:
    for parent in environment.parents:
        if not any(within(parent, root) for root in roots):
            break
        if (parent / "pyproject.toml").is_file():
            return parent
    return None


def locked_project(project: Path | None) -> bool:
    if project is None:
        return False
    try:
        metadata = tomllib.loads((project / "pyproject.toml").read_text())
        lock = tomllib.loads((project / "uv.lock").read_text())
        return bool(metadata) and isinstance(lock.get("version"), int)
    except (OSError, ValueError):
        return False


def tree_info(path: Path, *, project=False, skips=()) -> tuple[int, float]:
    """Allocated bytes and newest modification time, without following links."""
    size = 0
    latest = 0.0
    inodes = set()

    def visit(target):
        nonlocal size, latest
        stat = target.lstat()
        latest = max(latest, stat.st_mtime)
        inode = (stat.st_dev, stat.st_ino)
        if inode not in inodes:
            size += stat.st_blocks * 512
            inodes.add(inode)

    visit(path)

    def onerror(error):
        raise error  # An incomplete assessment must not allow deletion.

    for directory, dirs, files in os.walk(path, followlinks=False, onerror=onerror):
        parent = Path(directory)
        if project and (parent / "pyvenv.cfg").is_file():
            dirs[:] = []
            continue
        dirs[:] = [
            name
            for name in dirs
            if not (parent / name).is_symlink()
            and not ignored(parent / name, skips)
            and (not project or name not in PRUNED)
        ]
        for name in files:
            if not ignored(parent / name, skips):
                visit(parent / name)
        for name in dirs:
            visit(parent / name)
    return size, latest


@dataclass
class Environment:
    path: Path
    config: dict[str, str]
    project: Path | None
    locked: bool
    size: int
    activity: float
    marker: str
    identity: tuple[int, int]

    @property
    def direct_delete(self):
        return "uv" in self.config and self.locked

    @property
    def kind(self):
        if self.direct_delete:
            return "uv environment with locked project"
        if "uv" in self.config:
            return "standalone/unlocked uv environment (export required)"
        return "plain virtual environment (export required)"


def inspect(
    path: Path, roots: list[Path], project_activity: dict[Path, float], skips=()
):
    config = configuration(path)
    size, activity = tree_info(path)
    project = find_project(path, roots)
    activity_root = project or path.parent
    if activity_root not in roots:
        if activity_root not in project_activity:
            project_activity[activity_root] = tree_info(
                activity_root,
                project=True,
                skips=skips,
            )[1]
        activity = max(activity, project_activity[activity_root])
    stat = path.stat()
    return Environment(
        path,
        config,
        project,
        locked_project(project),
        size,
        activity,
        (path / "pyvenv.cfg").read_text(),
        (stat.st_dev, stat.st_ino),
    )


def human_size(size):
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return ""


def age_days(value):
    match = re.fullmatch(r"(\d+)([dwm]?)", value)
    if not match:
        raise argparse.ArgumentTypeError("use an age such as 90d, 12w or 3m")
    return int(match[1]) * {"": 1, "d": 1, "w": 7, "m": 30}[match[2]]


def interpreter(path):
    for name in ("python", "python3"):
        candidate = path / "bin" / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise ValueError("environment interpreter is missing or not executable")


def export_requirements(environment: Environment) -> Path:
    python = interpreter(environment.path)
    commands = [[str(python), "-m", "pip", "freeze", "--all", "--local"]]
    if shutil.which("uv"):
        commands.append(["uv", "pip", "freeze", "--python", str(python)])
    errors = []
    for command in commands:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if result.returncode == 0:
            requirements = result.stdout
            break
        errors.append(result.stderr.strip())
    else:
        raise ValueError("requirements export failed: " + "; ".join(errors))

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output = (
        environment.path.parent
        / f"requirements-from-{environment.path.name}-{timestamp}.txt"
    )
    with output.open("x") as handle:
        handle.write(f"# Environment: {environment.path}\n")
        handle.write(
            f"# Python: {environment.config.get('version_info', environment.config.get('version', 'unknown'))}\n"
        )
        handle.write(requirements)
    return output


def validate(environment: Environment, roots: list[Path], skips: list[Path]):
    path = environment.path
    if path.is_symlink() or path.resolve() != path:
        raise ValueError("refusing a symlinked environment path")
    stat = path.stat()
    if (stat.st_dev, stat.st_ino) != environment.identity:
        raise ValueError("environment directory changed during review")
    if not any(within(path, root) and path != root for root in roots):
        raise ValueError("environment is not inside a scan root")
    if ignored(path, skips):
        raise ValueError("environment is in a skipped directory")
    active = os.environ.get("VIRTUAL_ENV")
    if active and path == Path(active).resolve():
        raise ValueError("refusing the active environment")
    if within(Path(sys.prefix).resolve(), path):
        raise ValueError("refusing venvclean's own environment")
    if (path / "pyvenv.cfg").read_text() != environment.marker:
        raise ValueError("environment configuration changed during review")
    interpreter(path)


def recovery(environment):
    if environment.direct_delete:
        return (
            f"UV_PROJECT_ENVIRONMENT={shlex.quote(str(environment.path))} "
            f"uv sync --frozen --project {shlex.quote(str(environment.project))}"
        )
    return "Export requirements, then recreate with the same Python version."


def export_recovery(environment, export):
    version = environment.config.get("version_info", environment.config.get("version"))
    python_option = f" --python {shlex.quote(version)}" if version else ""
    system_option = (
        " --system-site-packages"
        if environment.config.get("include-system-site-packages") == "true"
        else ""
    )
    return (
        f"uv venv{python_option}{system_option} {shlex.quote(str(environment.path))}\n"
        f"uv pip install --python {shlex.quote(str(environment.path / 'bin' / 'python'))} "
        f"-r {shlex.quote(str(export))}"
    )


def review(environments, roots, skips, *, ask=input):
    removed = 0
    removed_size = 0
    exports = 0
    for index, environment in enumerate(environments, 1):
        print(f"\n[{index}/{len(environments)}] {environment.path}")
        print(f"  Size on disk: {human_size(environment.size)} (estimate)")
        print(
            f"  Last modified: {dt.datetime.fromtimestamp(environment.activity):%Y-%m-%d}"
        )
        print(f"  Kind: {environment.kind}")
        print(
            f"  Python: {environment.config.get('version_info', environment.config.get('version', 'unknown'))}"
        )
        if "uv" in environment.config:
            print(f"  uv: {environment.config['uv']}")
        print(f"  Project: {environment.project or 'not found'}")
        print(f"  Recover: {recovery(environment)}")
        prompt = (
            "[k]eep [d]elete [e]xport then delete [q]uit: "
            if environment.direct_delete
            else "[k]eep [e]xport then delete [q]uit: "
        )
        while True:
            choice = ask(prompt).strip().lower() or "k"
            if choice in {"k", "e", "q", "s"} or (
                choice == "d" and environment.direct_delete
            ):
                break
            print("Choose one of the listed actions.")
        if choice in {"q", "s"}:
            break
        if choice == "k":
            continue
        try:
            validate(environment, roots, skips)
            export = None
            if choice == "e":
                export = export_requirements(environment)
                exports += 1
                print(f"  Saved requirements: {export}")
                print(f"  Recreate with:\n{export_recovery(environment, export)}")
            if (
                ask("Permanently delete this environment? [y/N]: ").strip().lower()
                != "y"
            ):
                continue
            validate(environment, roots, skips)
            if choice == "d" and not locked_project(environment.project):
                raise ValueError("locked project is no longer available")
            if not environment.direct_delete and (
                export is None or not export.is_file()
            ):
                raise ValueError("requirements export is required before deletion")
            shutil.rmtree(environment.path)
            removed += 1
            removed_size += environment.size
            print("  Removed.")
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            print(f"  Kept/cleanup failed: {error}", file=sys.stderr)
    print(
        f"\nRemoved {removed} environments ({human_size(removed_size)} estimated); saved {exports} exports."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Review old Python environments and reclaim space interactively."
    )
    parser.add_argument("roots", nargs="*", help="scan roots (default: home directory)")
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="DIRECTORY",
        help="exclude a directory and descendants; repeatable",
    )
    parser.add_argument(
        "--older-than",
        type=age_days,
        default=90,
        metavar="AGE",
        help="minimum inactivity age (default: 90d; weeks/months also accepted)",
    )
    parser.add_argument(
        "--all", action="store_true", help="include recently modified environments"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list candidates without prompts, exports or deletion",
    )
    args = parser.parse_args()
    roots = [
        Path(value).expanduser().resolve() for value in args.roots or [str(Path.home())]
    ]
    skips = [Path(value).expanduser().resolve() for value in args.skip]
    if os.environ.get("VIRTUAL_ENV"):
        skips.append(Path(os.environ["VIRTUAL_ENV"]).resolve())
    if sys.prefix != sys.base_prefix:
        skips.append(Path(sys.prefix).resolve())
    if any(not root.is_dir() for root in roots):
        parser.error("every scan root must be an existing directory")
    if not args.dry_run and not sys.stdin.isatty():
        parser.error(
            "interactive cleanup requires a terminal; use --dry-run for a report"
        )
    project_activity = {}
    environments = []
    found = 0
    cutoff = time.time() - args.older_than * 86400
    print(
        f"Scanning {', '.join(map(str, roots))}; age threshold: {args.older_than} days",
        flush=True,
    )
    for path in discover(roots, skips):
        found += 1
        print(f"Inspecting {path}", flush=True)
        try:
            environment = inspect(path, roots, project_activity, skips)
            validate(environment, roots, skips)
            if args.all or environment.activity < cutoff:
                environments.append(environment)
        except (OSError, ValueError) as error:
            print(f"Skipping {path}: {error}", file=sys.stderr)
    environments.sort(key=lambda item: item.size, reverse=True)
    print(
        f"\nFound {found} environments; {len(environments)} eligible; {human_size(sum(item.size for item in environments))} potentially reclaimable (estimate)."
    )
    if args.dry_run:
        for environment in environments:
            print(
                f"{human_size(environment.size):>12}  {environment.kind}  {environment.path}"
            )
        return
    try:
        review(environments, roots, skips)
    except (EOFError, KeyboardInterrupt):
        print("\nStopped.")
