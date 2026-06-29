# Update Guide

Keep this suite easy for other agents to learn.

## Update Rules

1. Keep `skills/a-share-stock-analysis/SKILL.md` short and router-focused.
2. Put detailed procedures in `workflows/*/WORKFLOW.md`.
3. Put reusable facts, schemas, checklists, and policies in `references/`.
4. Put deterministic checks in `scripts/`.
5. Update both root `manifest.json` and skill-level `manifest.json` when paths change.
6. Run validation before publishing changes.

## Local Validation

From the repository root:

```powershell
python skills/a-share-stock-analysis/scripts/validate_holdings_csv.py --help
python skills/a-share-stock-analysis/scripts/validate_market_dataset.py --help
python -m compileall skills/a-share-stock-analysis/scripts
```

If this repository is copied into the shared skills library, run the shared audit script after changing skills:

```powershell
C:\Users\liuji\Desktop\Skills\tools\Audit-Skills.ps1
```

On this machine the shared library may also appear under:

```powershell
C:\Users\liuji\Desktop\科研Skills\
```

Use the path that exists on the current machine.

## Versioning

Use semantic versions in `skills/a-share-stock-analysis/manifest.json`.

- Patch: wording, template, or validation refinements
- Minor: new workflow, new script, new reference
- Major: changed routing model or output contract

