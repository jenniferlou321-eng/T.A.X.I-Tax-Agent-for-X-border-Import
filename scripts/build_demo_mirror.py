#!/usr/bin/env python3
"""build_demo_mirror.py — 用真实 corpus 内容布置「上游更新」演示(hold-back staging)。

**不编造任何税法文本。** 做法:从 corpus 里挑一批**冷门主题**(遗产税 / 资本利得 /
信托)的真实 source,把它们「预留」起来,模拟「这些内容上游刚发布、本地还没收录」:

  - NEW 示例:整条真实 source 从 local 移出、只放进 mirror → diff 视为 NEW。
  - MODIFIED 示例:某多-chunk 真 source 的**最后一段**从 local 移出、mirror 保留
    完整 → 两边正文哈希不同 → diff 视为 MODIFIED。

点「应用更新」后,这些**真实内容**合回 local(NEW 整条加回、MODIFIED 补回最后
一段),知识库恢复完整,agent 即可检索到刚「上线」的内容。

为什么选冷门税种:嘉汉演示主线是 UK VAT + CN,遗产税/资本利得/信托与主线无关,
预留期间即使 agent 被问到也只是「暂未收录」,不影响主演示。

幂等 / 可重跑:每次 stage 都从**干净基线** `.chunks_baseline.jsonl` 重建 local,
反复跑不会叠加污染。基线不存在时,首次以当前 local 为基线。

用法:
    python scripts/build_demo_mirror.py            # 布置演示(stage)
    python scripts/build_demo_mirror.py --clean    # 撤销:还原 local、清空 mirror
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# 项目根:scripts/ 的上一级
_ROOT = Path(__file__).resolve().parent.parent
_LOCAL_CORPUS = _ROOT / "data" / "tax_corpus" / "chunks_with_tags.jsonl"
_BASELINE = _ROOT / "data" / "tax_corpus" / ".chunks_baseline.jsonl"
_MIRROR_DIR = _ROOT / "data" / "tax_corpus_mirror"
_MIRROR_PATH = _MIRROR_DIR / "chunks_with_tags.jsonl"

# ════════════════════════════════════════════════════════════
# 预留集 — 全是 corpus 里真实存在的冷门 source(零编造)
# ════════════════════════════════════════════════════════════
# NEW:整条预留(从 local 移出,放进 mirror)
_NEW_SOURCE_IDS = [
    # 遗产税手册导言(纯 inheritance_tax)
    "hmrc-internal-manuals__inheritance-tax-manual__ihtm01001",
    # 营业资产赠与减免:限制(capital_gains_tax + inheritance_tax)
    "hmrc-internal-manuals__capital-gains-manual__cg66886",
    # 裸信托示例(capital_gains_tax / 信托)
    "hmrc-internal-manuals__capital-gains-manual__cg34380",
]

# MODIFIED:预留这些 source 的「最后一段」(local 缺末段,mirror 完整)
_MODIFIED_SOURCE_IDS = [
    # 合伙:实务声明 D12 全文(6 段)
    "hmrc-internal-manuals__capital-gains-manual__cg27170",
]


# ════════════════════════════════════════════════════════════
# 工具
# ════════════════════════════════════════════════════════════
def _load_lines(path: Path) -> list[dict]:
    """读 JSONL → list[dict],保持原始行顺序。"""
    out: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _atomic_write(path: Path, chunks: list[dict]) -> None:
    """原子写 JSONL(先写 .tmp 再 replace)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _ensure_baseline(local_path: Path, baseline_path: Path) -> None:
    """基线不存在时,以当前 local 为干净基线建立一份。"""
    if not baseline_path.exists():
        if not local_path.exists():
            raise SystemExit(f"[build_demo_mirror] 本地 corpus 不存在:{local_path}")
        _atomic_write(baseline_path, _load_lines(local_path))
        print(f"[build_demo_mirror] 已用当前 corpus 建立基线:{baseline_path}")


def _last_chunk_index(chunks: list[dict], source_id: str) -> int:
    """返回某 source_id 的最大 chunk_index(用于挑「最后一段」)。"""
    idxs = [c.get("chunk_index", 0) for c in chunks if c.get("source_id") == source_id]
    return max(idxs) if idxs else -1


# ════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════
def stage_demo(
    local_path: Path = _LOCAL_CORPUS,
    mirror_path: Path = _MIRROR_PATH,
    baseline_path: Path = _BASELINE,
) -> dict:
    """从干净基线布置演示:预留真实冷门 source 到 mirror。

    Returns:
        摘要 dict:{new_sources, modified_sources, local_chunks, mirror_chunks}
    """
    _ensure_baseline(local_path, baseline_path)
    baseline = _load_lines(baseline_path)

    new_set = set(_NEW_SOURCE_IDS)
    mod_set = set(_MODIFIED_SOURCE_IDS)

    # 校验:预留的 source_id 必须真实存在于基线
    present = {c.get("source_id") for c in baseline}
    missing = (new_set | mod_set) - present
    if missing:
        raise SystemExit(
            "[build_demo_mirror] 以下预留 source 不在基线 corpus 中,请检查 id:\n  "
            + "\n  ".join(sorted(missing))
        )

    # 每个 MODIFIED source 的「最后一段」chunk_index
    last_idx = {sid: _last_chunk_index(baseline, sid) for sid in mod_set}

    local_out: list[dict] = []
    mirror_out: list[dict] = []
    for c in baseline:
        sid = c.get("source_id")
        if sid in new_set:
            # NEW:整条移出 local,放进 mirror
            mirror_out.append(c)
            continue
        if sid in mod_set:
            # MODIFIED:mirror 留完整;local 去掉最后一段
            mirror_out.append(c)
            if c.get("chunk_index", 0) != last_idx[sid]:
                local_out.append(c)
            continue
        # 其它:原样留在 local
        local_out.append(c)

    _atomic_write(local_path, local_out)
    _atomic_write(mirror_path, mirror_out)

    return {
        "new_sources": list(_NEW_SOURCE_IDS),
        "modified_sources": list(_MODIFIED_SOURCE_IDS),
        "local_chunks": len(local_out),
        "mirror_chunks": len(mirror_out),
        "baseline_chunks": len(baseline),
    }


def clean(
    local_path: Path = _LOCAL_CORPUS,
    mirror_path: Path = _MIRROR_PATH,
    baseline_path: Path = _BASELINE,
) -> dict:
    """撤销演示布置:从基线还原 local,删除 mirror。"""
    _ensure_baseline(local_path, baseline_path)
    baseline = _load_lines(baseline_path)
    _atomic_write(local_path, baseline)
    if mirror_path.exists():
        mirror_path.unlink()
    return {"restored_chunks": len(baseline), "mirror_removed": True}


def main() -> None:
    ap = argparse.ArgumentParser(description="布置/撤销知识库「上游更新」演示(真实内容预留)")
    ap.add_argument("--clean", action="store_true", help="撤销:还原 local、清空 mirror")
    args = ap.parse_args()

    if args.clean:
        summary = clean()
        print(f"[build_demo_mirror] 已撤销演示布置。")
        print(f"  local 还原至 {summary['restored_chunks']} 段,mirror 已删除。")
        return

    summary = stage_demo()
    print(f"[build_demo_mirror] 已布置演示(真实内容预留,零编造)。")
    print(f"  基线总段数 : {summary['baseline_chunks']}")
    print(f"  NEW  (整条预留):")
    for sid in summary["new_sources"]:
        print(f"    - {sid}")
    print(f"  MODIFIED (预留末段):")
    for sid in summary["modified_sources"]:
        print(f"    - {sid}")
    print(f"  local  现有 {summary['local_chunks']} 段 / mirror {summary['mirror_chunks']} 段。")
    print(f"  → 点「模拟收到上游更新」即可检出 "
          f"{len(summary['new_sources'])} NEW + {len(summary['modified_sources'])} MODIFIED。")


if __name__ == "__main__":
    main()
