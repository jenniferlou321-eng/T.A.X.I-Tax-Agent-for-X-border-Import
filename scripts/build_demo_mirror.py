#!/usr/bin/env python3
"""build_demo_mirror.py — 生成知识库「上游更新」演示用的 mirror 文件。

用途(DEMO STAGING,非生产):
    模拟「HMRC / GOV.UK 上游官网发布了新内容」的场景,产出一个
    data/tax_corpus_mirror/chunks_with_tags.jsonl,让
    `GET /api/corpus/check-updates` 能真实检出:
      - 1 条 MODIFIED:一篇真实的 VAT 罚则 source,正文被改(模拟口径更新)
      - 1 条 NEW:一条本地 corpus 里不存在的新 source(2026 跨境数字服务新规)

    diff 在 source_id 级做哈希对比(见 backend/services/corpus_sync.py),
    所以:改 MODIFIED source 的 text → 哈希变 → MODIFIED;
          造一个新 source_id → 本地没有 → NEW。

设计:从真 corpus 派生(而非手写 JSONL),保证 chunk 的十几个字段
      (chunk_id / local_file / text_length / retrieved_at / status …)全部齐全,
      避免手写漏字段导致 diff / apply 行为异常。

幂等:可反复重跑,每次覆盖写 mirror 文件。

用法:
    python scripts/build_demo_mirror.py
"""
from __future__ import annotations

import json
from pathlib import Path

# 项目根:scripts/ 的上一级
_ROOT = Path(__file__).resolve().parent.parent
_LOCAL_CORPUS = _ROOT / "data" / "tax_corpus" / "chunks_with_tags.jsonl"
_MIRROR_DIR = _ROOT / "data" / "tax_corpus_mirror"
_MIRROR_PATH = _MIRROR_DIR / "chunks_with_tags.jsonl"

# 拿来做 MODIFIED 的真实 VAT 罚则 source(tax_tags = ['vat','hmrc_penalties_and_interest'])
_MODIFIED_SOURCE_ID = (
    "hmrc-internal-manuals__alcohol-wholesaler-registration-scheme__awrs100300"
)

# 模拟「HMRC 更新了 VAT 滞纳金/罚则口径」的新正文(贴合嘉汉 UK VAT 案例)
_MODIFIED_TEXT_PREFIX = (
    "【2026 更新】Late-payment and VAT default penalties — revised regime\n"
    "From 1 January 2026, HMRC applies a daily-interest late-payment penalty to "
    "outstanding VAT. The first penalty arises at 15 days overdue (3% of the tax "
    "outstanding), a second penalty accrues daily thereafter at 10% per annum until "
    "paid. This replaces the previous fixed default-surcharge percentages.\n\n"
)

# NEW source 的元数据
_NEW_SOURCE_ID = "hmrc-vat-notice-700-update-2026"
_NEW_TITLE = "VAT Notice 700:2026 年新规 — 跨境数字服务申报口径"
_NEW_URL = "https://www.gov.uk/guidance/vat-notice-700-2026-cross-border-digital-services"
_NEW_TEXT = (
    "VAT Notice 700 (2026 update) — cross-border digital services\n"
    "From 1 January 2026, UK-established businesses supplying digital services to "
    "overseas customers must report the place-of-supply determination on the VAT "
    "return using the new box-6 supplementary breakdown. B2B reverse-charge supplies "
    "remain outside the scope of UK output tax, but must be recorded for audit. "
    "Businesses with cross-border digital revenue above £85,000 should review their "
    "registration position under the revised threshold rules."
)


def _read_source_chunks(corpus_path: Path, source_id: str) -> list[dict]:
    """从 corpus 读出指定 source_id 的全部 chunk(按 chunk_index 排序)。"""
    chunks: list[dict] = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            if c.get("source_id") == source_id:
                chunks.append(c)
    chunks.sort(key=lambda c: c.get("chunk_index", 0))
    return chunks


def _build_modified_chunks(corpus_path: Path) -> list[dict]:
    """取真实 VAT 罚则 source,改其首个 chunk 的 text → 产出 MODIFIED。"""
    chunks = _read_source_chunks(corpus_path, _MODIFIED_SOURCE_ID)
    if not chunks:
        raise SystemExit(
            f"[build_demo_mirror] 在本地 corpus 找不到 source_id={_MODIFIED_SOURCE_ID};"
            f"\n  请确认 {corpus_path} 存在且包含该 source。"
        )
    head = dict(chunks[0])
    new_text = _MODIFIED_TEXT_PREFIX + head.get("text", "")
    head["text"] = new_text
    head["text_length"] = len(new_text)
    head["last_updated"] = "2026-01-01"
    chunks[0] = head
    return chunks


def _build_new_chunk(template: dict) -> dict:
    """照真 chunk 的字段结构造一条全新 source(单 chunk)→ 产出 NEW。"""
    c = dict(template)  # 复制字段骨架,保证字段齐全
    c["chunk_id"] = f"{_NEW_SOURCE_ID}__chunk_0001"
    c["source_id"] = _NEW_SOURCE_ID
    c["title"] = _NEW_TITLE
    c["url"] = _NEW_URL
    c["source_authority"] = "HMRC"
    c["source_type"] = "guidance"
    c["collection"] = "guidance"
    c["tax_type"] = "VAT"
    c["local_file"] = f"demo_mirror/{_NEW_SOURCE_ID}.txt"
    c["text"] = _NEW_TEXT
    c["text_length"] = len(_NEW_TEXT)
    c["chunk_index"] = 1
    c["chunk_count"] = 1
    c["effective_from"] = "2026-01-01"
    c["effective_to"] = None
    c["last_updated"] = "2026-01-01"
    c["status"] = "current"
    c["retrieved_at"] = "2026-06-15T00:00:00+00:00"
    c["tax_tags"] = ["vat", "hmrc_penalties_and_interest"]
    return c


def main() -> None:
    if not _LOCAL_CORPUS.exists():
        raise SystemExit(f"[build_demo_mirror] 本地 corpus 不存在:{_LOCAL_CORPUS}")

    modified_chunks = _build_modified_chunks(_LOCAL_CORPUS)
    new_chunk = _build_new_chunk(modified_chunks[0])

    all_chunks = modified_chunks + [new_chunk]

    _MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    with open(_MIRROR_PATH, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"[build_demo_mirror] 已写入 {_MIRROR_PATH}")
    print(f"  MODIFIED source: {_MODIFIED_SOURCE_ID} ({len(modified_chunks)} chunk)")
    print(f"  NEW      source: {_NEW_SOURCE_ID} (1 chunk)")
    print(f"  总计 {len(all_chunks)} 个 chunk。")


if __name__ == "__main__":
    main()
