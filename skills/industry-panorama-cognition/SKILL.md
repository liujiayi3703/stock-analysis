---
name: industry-panorama-cognition
description: 股票行业全景认知技能。Use when 用户要求分析公司、分析股票、个股研究、持仓复盘、行业全景、细分领域、产业链位置、上游/中游/下游、行业影响、技术壁垒、独角兽技术、护城河、商业模式、概念讲解、童话/寓言/比喻解释，或需要提升对一只股票背后行业地图的理解。
---

# 行业全景认知

## Purpose

Use this skill to add a cognition layer to stock analysis. The goal is to help the user understand what the company actually does, where it sits in the value chain, how it affects the industry, and whether any rare capability may be hard to copy.

This skill complements valuation, technical analysis, fund-flow analysis, UZI analysis, and portfolio review. It should not replace data verification or risk controls.

## Always Cover

For every company or material holding analysis, include:

1. 细分领域: the exact product/service segment, not only a broad industry label.
2. 产业链位置: upstream, midstream, downstream, platform/infrastructure, or cross-chain integrator.
3. 上游依赖: materials, equipment, technology, licenses, data, capacity, or suppliers.
4. 下游客户: end users, channels, enterprise customers, government procurement, or ecosystem partners.
5. 行业影响: whether the company changes cost, efficiency, standards, supply pattern, demand creation, localization, or bargaining power.
6. 稀缺能力: technology, process, data, brand, channel, certification, license, ecosystem, or cost curve advantage.
7. 类比讲解: one simple but not childish analogy when a concept is unfamiliar.

Load `references/template.md` for the exact output table and analogy rules.

## Evidence Discipline

Separate:

- facts: filings, announcements, annual reports, investor relations, exchange disclosures, industry association data, official policy, verified product/customer evidence;
- inference: value-chain position, scarcity, moat, profit-pool control, technology importance;
- unknowns: what still needs verification before making a strong claim.

Do not call a capability "unicorn-like" unless there is evidence of hard replication, such as customer validation, process know-how, regulatory/license scarcity, ecosystem lock-in, cost curve advantage, or repeated commercial wins. Patents alone are not enough.

## Minimal Output

If the user asks for a short answer, still include a compact version:

```markdown
行业全景一句话：
- 这家公司属于【细分领域】，大致处在产业链【位置】；它真正要看的不是概念热度，而是【谁离不开它】和【它能不能把行业变化变成自己的利润】。
```
