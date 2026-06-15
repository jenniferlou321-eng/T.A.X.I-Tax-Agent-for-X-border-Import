"""Skill 仓库结构单测(离线,不需 API key)。

对应实现计划组 D。校验 backend/agent/skill_plugins/ 下的 local plugin
目录结构、SKILL.md frontmatter、plugin.json,以及 engine 的插件推距函数。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.agent.engine as engine

_SKILL_ROOT = Path(engine.__file__).resolve().parent / "skill_plugins"

# 期望的 (plugin, [skill 目录名]) —— 连字符命名
_EXPECTED = {
    "uk": ["vat", "corporation-tax", "paye", "self-assessment", "stamp-duty"],
    "testland": ["vat"],
    "cn": ["cn-vat", "cn-cit"],
}


def _parse_frontmatter(text: str) -> dict[str, str]:
    """极简 YAML frontmatter 解析:取首尾 --- 之间的 key: value 行。"""
    assert text.startswith("---\n"), "SKILL.md 必须以 frontmatter 开头"
    end = text.index("\n---", 4)
    block = text[4:end]
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"')
    return out


@pytest.mark.parametrize("cc,skills", _EXPECTED.items())
def test_plugin_json_valid_and_name_matches_dir(cc, skills):
    manifest = _SKILL_ROOT / cc / ".claude-plugin" / "plugin.json"
    assert manifest.is_file(), f"缺 {manifest}"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data.get("name") == cc, f"plugin.json name 应 == 目录名 {cc}"


@pytest.mark.parametrize("cc,skills", _EXPECTED.items())
def test_skill_md_present_with_frontmatter(cc, skills):
    for skill in skills:
        md = _SKILL_ROOT / cc / "skills" / skill / "SKILL.md"
        assert md.is_file(), f"缺 SKILL.md: {md}"
        fm = _parse_frontmatter(md.read_text(encoding="utf-8"))
        assert fm.get("name"), f"{md} frontmatter 缺 name"
        assert fm.get("description"), f"{md} frontmatter 缺 description"


def test_skill_dir_names_use_hyphens_not_underscores():
    for cc, skills in _EXPECTED.items():
        for skill in skills:
            assert "_" not in skill, f"skill 目录名应用连字符: {skill}"


def test_derive_skill_plugins_from_registry_keys():
    """engine 推距函数:仅对有 skill 目录的国家产出 local plugin。"""
    keys = [
        ("uk", "vat"), ("uk", "corporation_tax"), ("uk", "paye"),
        ("uk", "self_assessment"), ("uk", "stamp_duty"),
        ("testland", "vat"),
        ("cn", "cn_vat"), ("cn", "cn_cit"),  # CN 有 skill 目录 → 产 plugin
        ("global", "tax_kb"),       # KB 不产 plugin
        ("de", "vat"),              # 无 skill 目录 → 跳过
    ]
    plugins = engine._derive_skill_plugins(keys)
    paths = {p["path"] for p in plugins}
    assert all(p["type"] == "local" for p in plugins)
    assert str(_SKILL_ROOT / "uk") in paths
    assert str(_SKILL_ROOT / "testland") in paths
    assert str(_SKILL_ROOT / "cn") in paths
    # de 无 skill 目录、global 不产 plugin
    assert not any(p.endswith("/de") or "global" in p for p in paths)


def test_expected_skill_names_hyphenated_namespaced():
    keys = [("uk", "vat"), ("uk", "corporation_tax"), ("testland", "vat"),
            ("cn", "cn_vat"), ("cn", "cn_cit"),
            ("global", "tax_kb"), ("de", "vat")]
    names = engine._expected_skill_names(keys)
    assert "uk:vat" in names
    assert "uk:corporation-tax" in names      # 下划线→连字符
    assert "testland:vat" in names
    assert "cn:cn-vat" in names               # CN 带前缀 tax_type → cn:cn-vat
    assert "cn:cn-cit" in names
    assert not any(n.startswith(("global", "de")) for n in names)


def test_all_mounted_slots_active_first_then_rest_empty_ws():
    active = [engine.JurisdictionSlot(jurisdiction="uk", tax_type="vat",
                                      workspace_path="/w/case")]
    keys = [("uk", "vat"), ("uk", "paye"), ("testland", "vat"),
            ("global", "tax_kb")]
    slots = engine._all_mounted_slots(active, keys)
    # active 在前且保留 workspace
    assert slots[0] == ("uk", "vat", "/w/case")
    # 其余已挂载税种补空 workspace,且不含 global
    rest = dict(((cc, tt), ws) for cc, tt, ws in slots[1:])
    assert rest[("uk", "paye")] == ""
    assert rest[("testland", "vat")] == ""
    assert not any(cc == "global" for cc, _, _ in slots)


def test_all_mounted_slots_includes_cn_now_that_it_is_supported():
    """CN 正式接入后 cn_vat/cn_cit 进 TAX_TYPES + 有 prompts/cn/*.py 段,
    mount-all 必须把它们纳入(不再跳过),且装配器不崩。"""
    from backend.agent.prompts import get_multi_jurisdiction_prompt

    active = [engine.JurisdictionSlot(jurisdiction="uk", tax_type="vat")]
    keys = [("uk", "vat"), ("cn", "cn_cit"), ("cn", "cn_vat"),
            ("testland", "vat"), ("global", "tax_kb")]
    slots = engine._all_mounted_slots(active, keys)
    mounted = {(cc, tt) for cc, tt, _ in slots}
    # CN 现已受支持 → 纳入
    assert ("cn", "cn_cit") in mounted
    assert ("cn", "cn_vat") in mounted
    assert ("uk", "vat") in mounted
    assert ("testland", "vat") in mounted
    # 装配器不抛 KeyError,且含 CN 段
    prompt = get_multi_jurisdiction_prompt(slots)
    assert "CN VAT" in prompt and "CN CIT" in prompt and len(prompt) > 0


def test_all_mounted_slots_skips_genuinely_unsupported_tax_types():
    """护栏仍在:对真正不在 TAX_TYPES 的合成 (cc,tt),mount-all 跳过、不崩。"""
    from backend.agent.prompts import get_multi_jurisdiction_prompt

    active = [engine.JurisdictionSlot(jurisdiction="uk", tax_type="vat")]
    keys = [("uk", "vat"), ("xx", "bogus"), ("de", "umsatzsteuer")]
    slots = engine._all_mounted_slots(active, keys)
    mounted = {(cc, tt) for cc, tt, _ in slots}
    assert ("xx", "bogus") not in mounted
    assert ("de", "umsatzsteuer") not in mounted
    assert ("uk", "vat") in mounted
    # 装配器不崩
    assert len(get_multi_jurisdiction_prompt(slots)) > 0


def test_all_mounted_slots_skips_invalid_active_slot():
    """即使用户把无效税种放进 active slot(如合成 xx:bogus),也不崩。"""
    active = [engine.JurisdictionSlot(jurisdiction="xx", tax_type="bogus")]
    keys = [("uk", "vat"), ("xx", "bogus")]
    slots = engine._all_mounted_slots(active, keys)
    mounted = {(cc, tt) for cc, tt, _ in slots}
    assert ("xx", "bogus") not in mounted
