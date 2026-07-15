#!/usr/bin/env python3
"""Route fuzzy user prompts to stock-analysis skills.

The router is intentionally dependency-free so generic agents can call it before
deciding which SKILL.md files to load.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path
from typing import Any


WORD_RE = re.compile(r"[a-z0-9][a-z0-9_.+\-/]*")
CJK_RE = re.compile(r"[\u3400-\u9fff]+")


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(text: Any) -> str:
    value = str(text or "").lower()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def flatten_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(flatten_strings(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(flatten_strings(item))
        return out
    return [str(value)]


def skill_phrases(skill: dict[str, Any]) -> list[str]:
    fields = [
        skill.get("id"),
        skill.get("name"),
        skill.get("description"),
        skill.get("aliases"),
        skill.get("keywords"),
    ]
    seen: set[str] = set()
    phrases: list[str] = []
    for field in fields:
        for phrase in flatten_strings(field):
            norm = normalize(phrase)
            if norm and norm not in seen:
                seen.add(norm)
                phrases.append(phrase)
    return phrases


def tokenize(text: str) -> set[str]:
    lower = normalize(text)
    tokens = set(WORD_RE.findall(lower))
    for seq in CJK_RE.findall(text):
        tokens.add(seq)
        if len(seq) >= 2:
            tokens.update(seq[i : i + 2] for i in range(len(seq) - 1))
        if len(seq) >= 3:
            tokens.update(seq[i : i + 3] for i in range(len(seq) - 2))
    return {token for token in tokens if len(token) > 0}


def score_skill(query: str, skill: dict[str, Any]) -> tuple[float, list[str]]:
    query_norm = normalize(query)
    query_tokens = tokenize(query)
    phrases = skill_phrases(skill)
    skill_text = " ".join(phrases)
    skill_tokens = tokenize(skill_text)

    score = 0.0
    reasons: list[str] = []
    matched_phrases: list[str] = []

    for phrase in phrases:
        phrase_norm = normalize(phrase)
        if len(phrase_norm) < 2:
            continue
        if phrase_norm in query_norm:
            score += 9.0
            matched_phrases.append(phrase)
        elif len(query_norm) >= 3 and query_norm in phrase_norm:
            score += 3.0
            matched_phrases.append(phrase)

    overlap = sorted(query_tokens & skill_tokens, key=lambda item: (-len(item), item))
    if overlap:
        score += min(12.0, len(overlap) * 0.55)
        reasons.append("token overlap: " + ", ".join(overlap[:8]))

    query_words = WORD_RE.findall(query_norm)
    skill_words = WORD_RE.findall(normalize(skill_text))
    fuzzy_hits: list[str] = []
    for word in query_words:
        if len(word) < 4:
            continue
        best = max((difflib.SequenceMatcher(None, word, item).ratio() for item in skill_words), default=0.0)
        if best >= 0.84:
            score += 0.35
            fuzzy_hits.append(word)
    if fuzzy_hits:
        reasons.append("fuzzy word match: " + ", ".join(fuzzy_hits[:5]))

    if matched_phrases:
        reasons.insert(0, "matched phrase: " + ", ".join(matched_phrases[:5]))

    return round(score, 3), reasons


def route(
    query: str,
    manifest: dict[str, Any],
    top: int = 8,
    min_score: float = 2.0,
    include_companions: bool = True,
) -> dict[str, Any]:
    skills = manifest.get("skills", [])
    by_id = {skill["id"]: skill for skill in skills}
    scored = []
    for skill in skills:
        score, reasons = score_skill(query, skill)
        if score > 0:
            scored.append(
                {
                    "id": skill["id"],
                    "entrypoint": skill["entrypoint"],
                    "path": skill["path"],
                    "score": score,
                    "role": "primary",
                    "description": skill.get("description", ""),
                    "reasons": reasons,
                }
            )

    scored.sort(key=lambda item: (-item["score"], item["id"]))
    primary = [item for item in scored if item["score"] >= min_score]
    if not primary:
        primary = scored[: min(3, len(scored))]

    selected = primary[:top]
    selected_ids = {item["id"] for item in selected}

    if include_companions:
        for item in list(selected[:2]):
            skill = by_id.get(item["id"], {})
            for companion_id in skill.get("companion_skills", []):
                if companion_id in selected_ids or companion_id not in by_id or len(selected) >= top:
                    continue
                companion = by_id[companion_id]
                selected.append(
                    {
                        "id": companion_id,
                        "entrypoint": companion["entrypoint"],
                        "path": companion["path"],
                        "score": 0.75,
                        "role": "companion",
                        "description": companion.get("description", ""),
                        "reasons": [f"companion of {item['id']}"],
                    }
                )
                selected_ids.add(companion_id)

    strong_primary = [item for item in primary if item["score"] >= min_score]
    close_second = len(strong_primary) >= 2 and (strong_primary[0]["score"] - strong_primary[1]["score"]) <= 2.0
    top_is_dominant = len(strong_primary) >= 2 and (strong_primary[0]["score"] - strong_primary[1]["score"]) >= 8.0
    broad_many = len(scored) >= 6 and (not strong_primary or scored[0]["score"] < 8.0)
    choice_required = (len(strong_primary) >= 4 and not top_is_dominant) or close_second or broad_many

    return {
        "query": query,
        "choice_required": choice_required,
        "choice_prompt": (
            "Matched several plausible skill paths. Ask the user to choose focus, or run the selected load_order "
            "from top to bottom when broad analysis is desired."
            if choice_required
            else ""
        ),
        "load_order": selected,
        "all_matches": scored[: max(top, 12)],
    }


def format_text(result: dict[str, Any]) -> str:
    lines = [f"Query: {result['query']}"]
    if result["choice_required"]:
        lines.append("Choice required: yes")
        lines.append(result["choice_prompt"])
    else:
        lines.append("Choice required: no")
    lines.append("")
    lines.append("Load order:")
    for item in result["load_order"]:
        reason = "; ".join(item.get("reasons") or [])
        lines.append(f"- {item['id']} ({item['role']}, score={item['score']}): {item['entrypoint']}")
        if reason:
            lines.append(f"  reason: {reason}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Route a fuzzy request to stock-analysis skills.")
    parser.add_argument("query", help="User request to route.")
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1] / "manifest.json")
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--min-score", type=float, default=2.0)
    parser.add_argument("--no-companions", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    result = route(
        args.query,
        manifest,
        top=args.top,
        min_score=args.min_score,
        include_companions=not args.no_companions,
    )
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
