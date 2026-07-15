# Update Guide

Keep this suite easy for other agents to learn.

## Update Rules

1. Keep `skills/ai-stock-picking/SKILL.md` as the sector-first stock-picking orchestrator.
2. Keep `skills/a-share-stock-analysis/SKILL.md` short and A-share-analysis focused.
3. Put detailed A-share and AI stock-picking procedures in `workflows/*/WORKFLOW.md`.
4. Put reusable facts, schemas, checklists, and policies in `references/`.
5. Put deterministic checks in `scripts/`.
6. Keep imported Serenity skills as independent folders under `skills/<skill-name>/`.
7. Update root `manifest.json` when skill paths or descriptions change.
8. Keep `scripts/skill_router.py` and `scripts/validate_skills.py` green when adding, removing, or renaming skills.
9. Run validation before publishing changes.

## Local Validation

From the repository root:

```powershell
$env:PYTHONUTF8=1
python scripts/validate_skills.py
python -m unittest discover tests
python scripts/skill_router.py "帮我分析目前股票持仓，下周怎么操作" --json
python skills/a-share-stock-analysis/scripts/validate_holdings_csv.py --help
python skills/a-share-stock-analysis/scripts/validate_market_dataset.py --help
python skills/a-share-stock-analysis/scripts/validate_trade_signals.py --help
python -m compileall skills/a-share-stock-analysis/scripts
python -m py_compile skills/stock-strategy-loop/scripts/run_loop.py
python -m unittest discover skills/stock-strategy-loop/tests
python skills/stock-strategy-loop/scripts/run_loop.py validate-positions --positions-json skills/stock-strategy-loop/examples/positions.sample.json
```

Validate each skill folder with Codex's skill validator:

```powershell
$env:PYTHONUTF8=1
$SKILL_CREATOR = "<path-to-skill-creator>"
python "$SKILL_CREATOR\scripts\quick_validate.py" skills\a-share-stock-analysis
python "$SKILL_CREATOR\scripts\quick_validate.py" skills\stock-strategy-loop
python "$SKILL_CREATOR\scripts\quick_validate.py" skills\ai-stock-picking
python "$SKILL_CREATOR\scripts\quick_validate.py" skills\serenity-alpha
python "$SKILL_CREATOR\scripts\quick_validate.py" skills\bayesian-intrinsic-growth-valuation
python "$SKILL_CREATOR\scripts\quick_validate.py" skills\gf-dma-health-index
python "$SKILL_CREATOR\scripts\quick_validate.py" skills\tam-adj-peg
python "$SKILL_CREATOR\scripts\quick_validate.py" skills\buy-side-equity-research-memo
```

If this repository is copied into the shared skills library, run the shared audit script after changing skills:

```powershell
& "<path-to-shared-skills>\tools\Audit-Skills.ps1"
```

On this machine the shared library may also appear under:

```powershell
<path-to-shared-skills>\
```

Use the path that exists on the current machine.

## Data-Source Contract

When updating `skills/stock-strategy-loop/scripts/run_loop.py`, keep the loop resilient to partial data:

- quote/history failures must lower confidence rather than fabricate prices
- fund-flow collection should normalize source-specific Chinese field names into stable internal keys
- event/news collection may degrade gracefully, but the report must expose the degradation in `data_coverage.errors`
- new output fields must be documented in `skills/stock-strategy-loop/references/loop-contracts.md`

## Versioning

Use semantic versions in `skills/a-share-stock-analysis/manifest.json`.

- Patch: wording, template, or validation refinements
- Minor: new workflow, new script, new reference
- Major: changed routing model or output contract
