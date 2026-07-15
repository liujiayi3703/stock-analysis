#!/usr/bin/env python3
"""Validate stock-analysis skill discovery metadata."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    lines = match.group(1).splitlines()
    data: dict[str, str] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if ":" not in line or line.startswith(" "):
            index += 1
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip().strip('"')
        if value in {">", "|"}:
            block: list[str] = []
            index += 1
            while index < len(lines) and lines[index].startswith(" "):
                block.append(lines[index].strip())
                index += 1
            data[key] = " ".join(block).strip()
            continue
        data[key] = value
        index += 1
    return data


def validate(manifest_path: Path) -> dict[str, Any]:
    root = manifest_path.parent
    skills_root = root / "skills"
    manifest = load_manifest(manifest_path)

    errors: list[str] = []
    warnings: list[str] = []
    skill_entries = manifest.get("skills", [])
    manifest_ids = [entry.get("id") for entry in skill_entries]
    duplicate_ids = sorted({skill_id for skill_id in manifest_ids if manifest_ids.count(skill_id) > 1})
    if duplicate_ids:
        errors.append("duplicate manifest ids: " + ", ".join(duplicate_ids))

    disk_ids = sorted(
        path.name
        for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    )
    manifest_id_set = set(manifest_ids)
    disk_id_set = set(disk_ids)
    missing_from_manifest = sorted(disk_id_set - manifest_id_set)
    stale_in_manifest = sorted(manifest_id_set - disk_id_set)
    if missing_from_manifest:
        errors.append("skills missing from manifest: " + ", ".join(missing_from_manifest))
    if stale_in_manifest:
        errors.append("manifest entries missing on disk: " + ", ".join(stale_in_manifest))

    default_entrypoint = manifest.get("default_entrypoint")
    if not default_entrypoint or not (root / default_entrypoint).exists():
        errors.append(f"default_entrypoint does not exist: {default_entrypoint}")

    for entry in skill_entries:
        skill_id = entry.get("id")
        path = root / str(entry.get("path", ""))
        entrypoint = root / str(entry.get("entrypoint", ""))
        if not skill_id:
            errors.append("manifest entry without id")
            continue
        if not path.exists():
            errors.append(f"{skill_id}: path does not exist: {entry.get('path')}")
            continue
        if not entrypoint.exists():
            errors.append(f"{skill_id}: entrypoint does not exist: {entry.get('entrypoint')}")
            continue

        frontmatter = parse_frontmatter(entrypoint)
        if frontmatter.get("name") != skill_id:
            errors.append(f"{skill_id}: SKILL.md name mismatch: {frontmatter.get('name')}")
        description = frontmatter.get("description", "").strip()
        if not description:
            errors.append(f"{skill_id}: missing SKILL.md description")
        if "????" in description:
            errors.append(f"{skill_id}: description contains replacement question marks")

        for resource_dir in entry.get("resource_dirs", []):
            if not (path / resource_dir).exists():
                errors.append(f"{skill_id}: resource_dir missing: {resource_dir}")

        if not entry.get("aliases"):
            warnings.append(f"{skill_id}: no aliases configured")
        if not entry.get("keywords"):
            warnings.append(f"{skill_id}: no keywords configured")

    for rel_path in manifest.get("recommended_generic_agent_files", []):
        if not (root / rel_path).exists():
            errors.append(f"recommended file does not exist: {rel_path}")

    return {
        "ok": not errors,
        "skill_count": len(disk_ids),
        "manifest_skill_count": len(skill_entries),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate skill manifest and top-level skill folders.")
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1] / "manifest.json")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    result = validate(args.manifest)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "ok" if result["ok"] else "failed"
        print(f"skill validation: {status}")
        print(f"skills on disk: {result['skill_count']}")
        print(f"skills in manifest: {result['manifest_skill_count']}")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
