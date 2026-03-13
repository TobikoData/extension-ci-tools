#!/usr/bin/env python3
# Create build metadata.json file for DuckDB extension builds
#
# This script generates a metadata file containing version information,
# build details, and commit hashes for both the extension and DuckDB.

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_git_command(cwd, command):
    """Run a git command and return the output, or 'unknown' on failure."""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def get_duckdb_info(repo_root, build_type):
    """Extract DuckDB version and commit from the duckdb submodule and built binary."""
    duckdb_dir = repo_root / "duckdb"

    if not duckdb_dir.exists():
        print(f"Warning: DuckDB submodule not found at {duckdb_dir}", file=sys.stderr)
        return {"git_describe": "unknown", "version": "unknown", "commit": "unknown"}

    git_dir = duckdb_dir / ".git"
    if not git_dir.exists():
        print(f"Warning: DuckDB directory is not a git repository", file=sys.stderr)
        return {"git_describe": "unknown", "version": "unknown", "commit": "unknown"}

    git_describe = run_git_command(duckdb_dir, ["git", "describe", "--tags", "--always", "--long"])
    commit = run_git_command(duckdb_dir, ["git", "rev-parse", "HEAD"])

    # Try to get actual version from built DuckDB binary
    actual_version = "unknown"
    binary_paths = [
        repo_root / "build" / build_type / "duckdb",
        repo_root / "build" / build_type / "duckdb.exe",
    ]

    for binary_path in binary_paths:
        if binary_path.exists():
            try:
                result = subprocess.run(
                    [str(binary_path), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # Parse output like: "v1.5.0-dev1754 (Development Version) c8267cbc21"
                if result.returncode == 0 and result.stdout:
                    parts = result.stdout.strip().split()
                    if parts:
                        actual_version = parts[0]  # First word is the version
                        break
            except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
                pass

    return {
        "git_describe": git_describe,
        "version": actual_version,
        "commit": commit
    }


def get_extension_info(repo_root):
    """Get the extension version and commit hash."""
    # Try to get tag at current HEAD
    tag = run_git_command(repo_root, ["git", "tag", "--points-at", "HEAD"])

    # Get commit hash
    commit = run_git_command(repo_root, ["git", "rev-parse", "HEAD"])
    short_commit = run_git_command(repo_root, ["git", "rev-parse", "--short", "HEAD"])

    # Extension version is tag if exists, otherwise short commit
    version = tag if tag and tag != "unknown" else short_commit

    return {"version": version, "commit": commit}


def create_metadata(args):
    """Generate metadata.json with build information."""
    # Determine repository root
    repo_root = Path.cwd()

    # Get version information
    duckdb_info = get_duckdb_info(repo_root, args.build_type)
    extension_info = get_extension_info(repo_root)

    # Build metadata structure
    metadata = {
        "extension_name": args.extension_name,
        "extension_version": extension_info["version"],
        "extension_commit": extension_info["commit"],
        "duckdb_version": duckdb_info["version"],
        "duckdb_git_describe": duckdb_info["git_describe"],
        "duckdb_commit": duckdb_info["commit"],
        "platform": args.platform,
        "build_type": args.build_type,
        "build_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workflow_run_id": args.workflow_run_id or "",
        "ci_tools_version": args.ci_tools_version or ""
    }

    # Determine output path
    output_dir = repo_root / "build" / args.build_type
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "metadata.json"

    # Write metadata file
    with open(output_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"Created metadata file: {output_file}")
    print(json.dumps(metadata, indent=2))

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Create build metadata.json for DuckDB extension builds'
    )

    parser.add_argument(
        '--extension-name',
        type=str,
        required=True,
        help='Name of the extension (e.g., sqlglot)'
    )

    parser.add_argument(
        '--build-type',
        type=str,
        required=True,
        help='Build type (e.g., release, debug)'
    )

    parser.add_argument(
        '--platform',
        type=str,
        required=True,
        help='Platform architecture (e.g., linux_amd64, osx_arm64)'
    )

    parser.add_argument(
        '--ci-tools-version',
        type=str,
        help='Version of extension-ci-tools (e.g., v1.4.1p)'
    )

    parser.add_argument(
        '--workflow-run-id',
        type=str,
        help='GitHub Actions workflow run ID'
    )

    args = parser.parse_args()

    try:
        return create_metadata(args)
    except Exception as e:
        print(f"Error creating metadata: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
