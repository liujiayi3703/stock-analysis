# Update Guide

Keep this suite easy for other agents to learn.

## Update Rules

1. Keep `skills/a-share-stock-analysis/SKILL.md` short and router-focused.
2. Put detailed A-share procedures in `workflows/*/WORKFLOW.md`.
3. Put reusable facts, schemas, checklists, and policies in `references/`.
4. Put deterministic checks in `scripts/`.
5. Keep imported Serenity skills as independent folders under `skills/<skill-name>/`.
6. Update root `manifest.json` when skill paths or descriptions change.
7. Run validation before publishing changes.

## Local Validation

From the repository root:

```powershell
python skills/a-share-stock-analysis/scripts/validate_holdings_csv.py --help
python skills/a-share-stock-analysis/scripts/validate_market_dataset.py --help
python -m compileall skills/a-share-stock-analysis/scripts
```

Validate each skill folder with Codex's skill validator:

```powershell
python C:\Users\liuji\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\a-share-stock-analysis
python C:\Users\liuji\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\serenity-alpha
python C:\Users\liuji\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\bayesian-intrinsic-growth-valuation
python C:\Users\liuji\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\gf-dma-health-index
python C:\Users\liuji\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\tam-adj-peg
python C:\Users\liuji\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\buy-side-equity-research-memo
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
