from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


skill_router = load_module("skill_router", ROOT / "scripts" / "skill_router.py")
validate_skills = load_module("validate_skills", ROOT / "scripts" / "validate_skills.py")


class SkillRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = skill_router.load_manifest(MANIFEST)

    def ids_for(self, query: str, top: int = 8) -> list[str]:
        result = skill_router.route(query, self.manifest, top=top)
        return [item["id"] for item in result["load_order"]]

    def test_manifest_covers_every_top_level_skill(self) -> None:
        result = validate_skills.validate(MANIFEST)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["skill_count"], result["manifest_skill_count"])

    def test_holding_loop_routes_to_strategy_loop_and_a_share(self) -> None:
        ids = self.ids_for("请根据最新截图对目前持仓复盘，并跑三年回测和参数优化")
        self.assertIn("stock-strategy-loop", ids[:3])
        self.assertIn("a-share-stock-analysis", ids)

    def test_plain_holding_analysis_routes_to_a_share(self) -> None:
        ids = self.ids_for("帮我分析目前股票持仓，下周怎么操作")
        self.assertIn("a-share-stock-analysis", ids[:3])

    def test_openclaw_value_prompt_routes_to_analyzer(self) -> None:
        ids = self.ids_for("用巴菲特和段永平框架看这只美股的估值和建仓")
        self.assertIn("openclaw-stock-analyzer", ids[:3])

    def test_mcp_auth_prompt_routes_to_api_key_skill(self) -> None:
        ids = self.ids_for("MCP API key 鉴权报401，帮我配置 Claude Code")
        self.assertIn("mcp-api-key-auth", ids[:3])

    def test_trap_prompt_routes_to_trap_detector(self) -> None:
        ids = self.ids_for("群里老师说这票必涨，帮我看看是不是杀猪盘")
        self.assertIn("uzi-trap-detector", ids[:3])

    def test_broad_stock_analysis_requires_choice(self) -> None:
        result = skill_router.route("股票分析", self.manifest, top=8)
        self.assertTrue(result["choice_required"], result)

    def test_stock_strategy_loop_release_manifest_is_complete(self) -> None:
        path = ROOT / "skills" / "stock-strategy-loop" / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))

        self.assertGreaterEqual(
            tuple(int(part) for part in manifest["version"].split(".")),
            (0, 2, 0),
        )
        self.assertEqual(
            set(manifest["scripts"]),
            {
                "scripts/run_loop.py",
                "scripts/market_context.py",
                "scripts/reporting.py",
            },
        )
        self.assertEqual(
            set(manifest["tests"]),
            {
                "tests/test_run_loop.py",
                "tests/test_market_context.py",
                "tests/test_reporting.py",
            },
        )
        self.assertIn("requests>=2.31,<3", manifest["python_dependencies"])

    def test_stock_strategy_loop_release_candidates_are_private_safe(self) -> None:
        skill = ROOT / "skills" / "stock-strategy-loop"
        manifest = json.loads(
            (skill / "manifest.json").read_text(encoding="utf-8")
        )
        relative_paths = [manifest["entrypoint"]]
        for field in ("references", "scripts", "tests", "examples", "evals"):
            relative_paths.extend(manifest.get(field, []))
        private_tokens = (
            "00" + "99",
            "牛" * 3,
            "002" + "943",
            "688" + "502",
            "301" + "382",
            "蜂" + "助手",
            "生活中的" + "资料",
        )
        windows_absolute = re.compile(r"[A-Za-z]:\\")
        unix_home = re.compile(r"/(?:Users|home)/[^/]+/")

        for relative in relative_paths:
            with self.subTest(path=relative):
                text = (skill / relative).read_text(encoding="utf-8")
                self.assertIsNone(windows_absolute.search(text))
                self.assertIsNone(unix_home.search(text))
                for token in private_tokens:
                    self.assertNotIn(token, text)

    def test_stock_strategy_loop_nonproduction_codes_use_reviewed_fixtures(self) -> None:
        skill = ROOT / "skills" / "stock-strategy-loop"
        manifest = json.loads((skill / "manifest.json").read_text(encoding="utf-8"))
        relative_paths = [manifest["entrypoint"]]
        for field in ("references", "tests", "examples", "evals"):
            relative_paths.extend(manifest.get(field, []))
        reviewed_fixture_codes = {
            "000001",
            "000002",
            "000003",
            "000004",
            "000005",
            "000006",
            "000007",
            "000101",
            "000123",
            "000202",
            "000301",
            "000302",
            "000303",
            "100000",
            "300101",
            "430001",
            "600000",
            "600101",
            "999999",
        }
        unexpected = {}
        for relative in relative_paths:
            text = (skill / relative).read_text(encoding="utf-8")
            codes = set(re.findall(r"(?<!\d)\d{6}(?!\d)", text))
            unreviewed = sorted(codes - reviewed_fixture_codes)
            if unreviewed:
                unexpected[relative] = unreviewed

        self.assertEqual(unexpected, {})

    def test_positions_schema_uses_the_synthetic_release_assets(self) -> None:
        skill = ROOT / "skills" / "stock-strategy-loop"
        sample = json.loads(
            (skill / "examples" / "positions.sample.json").read_text(encoding="utf-8")
        )
        schema_text = (skill / "references" / "positions-schema.md").read_text(
            encoding="utf-8"
        )
        match = re.search(r"```json\s*(\{.*?\})\s*```", schema_text, re.DOTALL)
        self.assertIsNotNone(match)
        documented = json.loads(match.group(1))

        for field in ("cash", "stock_value", "total_assets"):
            with self.subTest(field=field):
                self.assertEqual(documented[field], sample[field])

    def test_root_gitignore_excludes_runtime_and_private_artifacts(self) -> None:
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (
            "__pycache__/",
            "*.py[cod]",
            ".stock-loop/",
            "positions.json",
            "Screenshot_*",
            ".env",
            ".venv/",
            ".superpowers/",
            "docs/superpowers/",
        ):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, text)

    def test_stock_monitor_test_suite_uses_portable_module_path(self) -> None:
        path = ROOT / "skills" / "stock-monitor-skill" / "scripts" / "test_suite.py"
        text = path.read_text(encoding="utf-8")

        self.assertNotIn("/home/wesley/", text)
        self.assertIn("Path(__file__).resolve().parent", text)


if __name__ == "__main__":
    unittest.main()
