#!/usr/bin/env python3
"""Restore Anytype objects from the export/ directory.

For each exported object:
- If it still exists in Anytype → update name, description, and body
- If it was deleted or doesn't exist → recreate it

Types and properties are restored first (idempotent — skips if they
already exist by key).
"""

import json
import sys
from pathlib import Path

import anytype_api

EXPORT_DIR = Path(__file__).parent / "export"


def restore_types(space_id: str, types: list[dict]):
    existing = {t["key"]: t for t in anytype_api.list_types(space_id)}
    for t in types:
        key = t["key"]
        if key in existing:
            continue
        try:
            anytype_api.create_type(
                space_id,
                name=t["name"],
                key=key,
                plural_name=t.get("plural_name", t["name"] + "s"),
                icon=t.get("icon"),
            )
            print(f"  Created type: {t['name']}")
        except Exception as e:
            print(f"  Skipping type {t['name']}: {e}")


def restore_properties(space_id: str, properties: list[dict]):
    existing = {p["key"]: p for p in anytype_api.list_properties(space_id)}
    for p in properties:
        key = p["key"]
        if key in existing:
            continue
        try:
            anytype_api.create_property(
                space_id,
                name=p["name"],
                key=key,
                format=p["format"],
            )
            print(f"  Created property: {p['name']}")
        except Exception as e:
            print(f"  Skipping property {p['name']}: {e}")


def restore_object(space_id: str, obj_data: dict, md_content: str | None):
    obj_id = obj_data["id"]
    name = obj_data.get("name", "untitled")
    type_key = obj_data.get("type", {}).get("key")
    description = ""
    body = md_content

    # Extract description from properties if present
    for prop in obj_data.get("properties", []):
        if prop.get("key") == "description":
            description = prop.get("text", "")
            break

    if anytype_api.object_exists(space_id, obj_id):
        fields = {"name": name}
        if description:
            fields["description"] = description
        if body:
            fields["body"] = body
        anytype_api.update_object(space_id, obj_id, **fields)
        print(f"  Updated: {name}")
    else:
        if not type_key:
            print(f"  Skipping {name}: no type_key")
            return
        fields = {}
        if description:
            fields["description"] = description
        if body:
            fields["body"] = body
        if obj_data.get("icon"):
            fields["icon"] = obj_data["icon"]
        anytype_api.create_object(space_id, type_key, name, **fields)
        print(f"  Recreated: {name}")


def restore_space(space_dir: Path, space_id: str):
    # Restore types
    types_file = space_dir / "_types.json"
    if types_file.exists():
        types = json.loads(types_file.read_text())
        restore_types(space_id, types)

    # Restore properties
    props_file = space_dir / "_properties.json"
    if props_file.exists():
        properties = json.loads(props_file.read_text())
        restore_properties(space_id, properties)

    # Restore objects
    for json_file in sorted(space_dir.rglob("*.json")):
        if json_file.name.startswith("_"):
            continue
        obj_data = json.loads(json_file.read_text())
        md_file = json_file.with_suffix(".md")
        md_content = md_file.read_text() if md_file.exists() else None
        # Strip the "# Title\n\n" prefix we add during export
        if md_content and md_content.startswith("# "):
            md_content = md_content.split("\n", 2)[-1].lstrip("\n")
        restore_object(space_id, obj_data, md_content)


def find_space_id(space_name: str) -> str | None:
    """Match an export directory name to a live space ID."""
    spaces = anytype_api.list_spaces()
    for s in spaces:
        name = s.get("name") or s["id"][:16]
        if name == space_name:
            return s["id"]
    return None


def main():
    if not EXPORT_DIR.exists():
        print("No export/ directory found.")
        sys.exit(1)

    for space_dir in sorted(EXPORT_DIR.iterdir()):
        if not space_dir.is_dir():
            continue
        space_name = space_dir.name
        space_id = find_space_id(space_name)
        if not space_id:
            print(f"Skipping '{space_name}': no matching space found")
            continue

        print(f"\nRestoring space: {space_name}")
        restore_space(space_dir, space_id)

    print("\nDone!")


if __name__ == "__main__":
    main()
