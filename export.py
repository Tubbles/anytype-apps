#!/usr/bin/env python3
"""Export all Anytype objects to Markdown files in the export/ directory."""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import anytype_api

EXPORT_DIR = Path(__file__).parent / "export"


def sanitize_filename(name: str) -> str:
    """Turn an object name into a safe filename."""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    return name or "untitled"


def export_space(space: dict) -> Path:
    """Export all objects from a space to markdown files. Returns the space dir."""
    space_id = space["id"]
    space_name = space.get("name") or space_id[:16]
    space_dir = EXPORT_DIR / sanitize_filename(space_name)
    space_dir.mkdir(parents=True, exist_ok=True)

    # Export types metadata
    types = anytype_api.list_types(space_id)
    types_file = space_dir / "_types.json"
    types_file.write_text(json.dumps(types, indent=2))

    # Export properties metadata
    properties = anytype_api.list_properties(space_id)
    props_file = space_dir / "_properties.json"
    props_file.write_text(json.dumps(properties, indent=2))

    # Search all objects
    objects = anytype_api.search_objects(space_id)
    print(f"  Found {len(objects)} objects in '{space_name}'")

    # Export each object with full details
    for obj in objects:
        obj_id = obj["id"]
        obj_name = obj.get("name", "untitled")
        obj_type = obj.get("type", {}).get("key", "unknown")

        obj_dir = space_dir / sanitize_filename(obj_type)
        obj_dir.mkdir(parents=True, exist_ok=True)
        filename = sanitize_filename(obj_name)

        # Fetch full object (includes markdown field)
        try:
            full = anytype_api.get_object(space_id, obj_id)
            obj_data = full.get("object", full)
        except Exception as e:
            print(f"    Warning: could not fetch '{obj_name}': {e}")
            obj_data = obj

        # Save full metadata as JSON
        meta_file = obj_dir / f"{filename}.json"
        meta_file.write_text(json.dumps(obj_data, indent=2))

        # Save markdown content if present
        markdown = obj_data.get("markdown", "")
        if markdown:
            md_file = obj_dir / f"{filename}.md"
            md_file.write_text(f"# {obj_name}\n\n{markdown}")

    return space_dir


def git_commit(message: str):
    """Stage everything in export/ and commit."""
    repo_root = Path(__file__).parent
    subprocess.run(["git", "add", "export/"], cwd=repo_root, check=True)

    # Check if there are staged changes
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo_root,
    )
    if result.returncode == 0:
        print("No changes to commit.")
        return

    subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True)
    print(f"Committed: {message}")


def main():
    print("Fetching spaces...")
    spaces = anytype_api.list_spaces()
    print(f"Found {len(spaces)} space(s)")

    for space in spaces:
        space_name = space.get("name") or space["id"][:16]
        print(f"\nExporting space: {space_name}")
        export_space(space)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    git_commit(f"Export {timestamp}")


if __name__ == "__main__":
    main()
