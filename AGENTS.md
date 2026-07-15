# Agent Loading Contract

This repository is a generic stock-analysis skill library. Agents should not load every file by default.

## Load Flow

1. Read `manifest.json`.
2. For fuzzy user wording, run:

```powershell
python scripts/skill_router.py "<user request>" --json
```

3. If `choice_required` is true, ask the user which direction to prioritize unless the user explicitly wants broad analysis.
4. Load each returned `entrypoint` in `load_order`.
5. Load workflow, reference, script, or template files only when the selected `SKILL.md` asks for them.

## Validation

From this folder:

```powershell
$env:PYTHONUTF8=1
python scripts/validate_skills.py
python -m unittest discover tests
```

Codex's external `quick_validate.py` also requires UTF-8 mode on Windows when skill files contain Chinese text:

```powershell
$env:PYTHONUTF8=1
$SKILL_CREATOR = "<path-to-skill-creator>"
python "$SKILL_CREATOR\scripts\quick_validate.py" skills\a-share-stock-analysis
```

## Routing Rule

Use the router's `load_order` as the authoritative dispatch suggestion. The top item is the primary skill; companion skills add supporting analysis such as industry panorama, data source access, investor panel review, or trap detection.

Investment outputs must separate verified facts, inference, uncertainty, risk controls, and non-advice boundaries. Do not auto-place trades.
