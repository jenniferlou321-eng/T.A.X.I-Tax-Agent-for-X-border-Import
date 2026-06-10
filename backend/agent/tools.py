"""TaxAgent Tools — 基于 claude-agent-sdk 的多管辖地税务工具集

解耦设计:
    - 不再硬编码 UK HMRC 工具
    - 通过 JurisdictionRegistry 动态获取各国工具实现 (AgentToolSet)
    - 为每个管辖地/税种创建独立的 MCP Server
    - 新增国家只需实现 AgentToolSet 接口并注册到 Registry

用法:
    from backend.agent.tools import create_mcp_servers, TOOL_ALLOWLIST_BY_JURISDICTION

    servers = create_mcp_servers(registry)
    # servers = {
    #     ("uk", "vat"): {"name": "tax_agent_uk_vat", "instance": <MCP server>},
    # }
"""

from __future__ import annotations

import json
from typing import Any

# ── SDK 导入（带优雅降级） ──
try:
    from claude_agent_sdk import tool, create_sdk_mcp_server
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

    def tool(name: str = "", description: str = "", input_schema: Any = None):
        def decorator(fn):
            fn._tool_name = name
            fn._tool_description = description
            fn._tool_schema = input_schema
            return fn
        return decorator

    def create_sdk_mcp_server(**kwargs):
        return None

from backend.models.tax_data import TaxType
from backend.registry import JurisdictionRegistry

# ═══════════════════════════════════════════════════════════
# Global Registry Reference (injected by server/main.py)
# ═══════════════════════════════════════════════════════════

_registry: JurisdictionRegistry | None = None


def set_registry(registry: JurisdictionRegistry) -> None:
    """在应用启动时注入全局 Registry"""
    global _registry
    _registry = registry


def get_registry() -> JurisdictionRegistry:
    if _registry is None:
        raise RuntimeError("JurisdictionRegistry not set. Call set_registry() first.")
    return _registry


# ═══════════════════════════════════════════════════════════
# Dynamic Tool Wrapper Factory
# ═══════════════════════════════════════════════════════════

def _resolve_method_name(tool_set, meta_name: str) -> str:
    """根据 MCP tool 名称解析到 tool_set 上实际的方法名

    工具元数据使用面向 LLM 的语义名（如 'get_vat_obligations'），
    而 tool_set 上是较短的实现名（如 'get_obligations'）。
    """
    if hasattr(tool_set, meta_name):
        return meta_name

    # 显式别名映射（处理特殊命名）
    aliases = {
        "calculate_corporation_tax": "calculate_return",
        "calculate_vat_return": "calculate_return",
        "calculate_self_assessment": "calculate_return",
        "calculate_paye": "calculate_return",
        "calculate_sdlt": "calculate_return",
        "get_corporation_tax_obligations": "get_obligations",
        "get_self_assessment_obligations": "get_obligations",
        "get_paye_obligations": "get_obligations",
        "get_vat_obligations": "get_obligations",
        "submit_corporation_tax": "submit_return",
        "submit_self_assessment": "submit_return",
        "submit_paye": "submit_return",
        "submit_vat_return": "submit_return",
        "submit_sdlt": "submit_return",
        "get_corporation_tax": "get_return",
        "get_self_assessment": "get_return",
        "get_paye": "get_return",
        "get_vat_return": "get_return",
        "get_sdlt": "get_return",
        "validate_corporation_tax": "validate_return",
        "validate_self_assessment": "validate_return",
        "validate_paye": "validate_return",
        "validate_vat_return": "validate_return",
        "validate_sdlt": "validate_return",
        "suggest_ct_optimization": "suggest_optimization",
        "suggest_optimization": "suggest_optimization",
    }
    if meta_name in aliases and hasattr(tool_set, aliases[meta_name]):
        return aliases[meta_name]

    # 常见映射：按税种前缀逐一尝试去除（不一定在开头）
    for prefix in ("vat_", "self_assessment_", "corporation_tax_", "paye_", "stamp_duty_"):
        if prefix in meta_name:
            candidate = meta_name.replace(prefix, "", 1)
            if hasattr(tool_set, candidate):
                return candidate
    raise AttributeError(
        f"Tool set {type(tool_set).__name__} has no method for meta name '{meta_name}'"
    )


# 各种税种 ID 在 LLM 视角下的常见命名，映射到 tool_set 上的 taxpayer_id
# 注意：不能包含 "period_key" 或 "nino" 这类可能被无意作为 taxpayer_id 的字段
_TAXPAYER_ID_KEYS = (
    "taxpayer_id", "vrn", "nino", "ctref", "empref", "utr", "transaction_id",
)


def _map_taxpayer_id(args: dict) -> dict:
    """将 LLM 传入的常见税种 ID 字段统一为 taxpayer_id

    不同工具的 input_schema 命名差异：
    - UK VAT: vrn
    - UK SA: nino
    - UK CT: ctref
    - UK PAYE: empref
    - UK SDLT: transaction_id

    但所有 AgentToolSet 的方法统一使用 taxpayer_id 参数。
    """
    if not isinstance(args, dict):
        return args

    if args.get("taxpayer_id"):
        return args

    for key in _TAXPAYER_ID_KEYS:
        val = args.get(key)
        if val:
            new_args = dict(args)
            new_args["taxpayer_id"] = new_args.pop(key)
            return new_args

    return args


def _make_tool_wrapper(tool_set, method_name: str, meta: dict):
    """为 AgentToolSet 的方法创建可被 @tool 装饰的异步函数

    Args:
        tool_set: AgentToolSet 实例
        method_name: 工具元数据中的语义名（如 'get_vat_obligations'）
        meta: 工具元数据（name, description, input_schema）

    Returns:
        被 @tool 装饰的 async 函数
    """
    actual_method = _resolve_method_name(tool_set, method_name)
    method = getattr(tool_set, actual_method)

    # 检查方法签名：如果接受单一 dict 参数（如 `def calculate(args: dict)`），
    # 则整个 args 作为单一参数传入；否则展开为 kwargs
    import inspect
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    # 跳过 self
    params = [p for p in params if p != "self"]
    takes_dict = (
        len(params) == 1
        and params[0] in ("args", "data", "params")
    )

    async def _wrapper(args: dict) -> dict:
        # 映射各种税种 ID 字段名到统一的 taxpayer_id
        mapped = _map_taxpayer_id(args)
        if takes_dict:
            return await method(mapped)
        return await method(**mapped)

    # 复制元数据用于 MCP Server 注册
    _wrapper._tool_name = meta["name"]
    _wrapper._tool_description = meta["description"]
    _wrapper._tool_schema = meta["input_schema"]

    # 应用 SDK 装饰器（如果可用）
    if SDK_AVAILABLE:
        return tool(
            meta["name"],
            meta["description"],
            meta["input_schema"],
        )(_wrapper)
    return _wrapper


# ═══════════════════════════════════════════════════════════
# MCP Server Factory
# ═══════════════════════════════════════════════════════════

def create_mcp_servers(registry: JurisdictionRegistry | None = None) -> dict[tuple[str, str], dict]:
    """为所有已注册的管辖地/税种创建 MCP Server

    Returns:
        {(country_code, tax_type_value): {"name": str, "instance": MCP server}}
    """
    if registry is None:
        registry = get_registry()

    if not SDK_AVAILABLE:
        return {}

    servers: dict[tuple[str, str], dict] = {}

    for adapter in registry._adapters.values():
        for tax_type in adapter.tax_types:
            tool_set = adapter.get_agent_tools(tax_type)
            if tool_set is None:
                continue

            server_name = f"tax_agent_{adapter.country_code}_{tax_type.value}"
            try:
                metadata = tool_set.get_tool_metadata()
            except Exception as e:
                print(f"[WARN] {server_name}: failed to read tool metadata: {e}")
                continue

            # 为每个工具创建包装函数
            wrapped_tools = []
            skipped: list[str] = []
            for meta in metadata:
                method_name = meta["name"]
                # 映射：工具名 -> 方法名（通常相同，但如果不同需要映射）
                try:
                    wrapped = _make_tool_wrapper(tool_set, method_name, meta)
                    wrapped_tools.append(wrapped)
                except AttributeError as e:
                    # 该 tool_set 上找不到对应方法 — 跳过这条工具，不影响其他工具的注册
                    skipped.append(f"{method_name} ({e})")

            if skipped:
                print(
                    f"[WARN] {server_name}: skipped {len(skipped)} tool(s) with "
                    f"unresolved methods: {'; '.join(skipped)}"
                )

            if not wrapped_tools:
                print(f"[WARN] {server_name}: no tools registered, skipping MCP server")
                continue

            mcp_server = create_sdk_mcp_server(
                name=server_name,
                version="1.0.0",
                tools=wrapped_tools,
            )

            if mcp_server:
                servers[(adapter.country_code, tax_type.value)] = {
                    "name": server_name,
                    "instance": mcp_server,
                }

    return servers


def get_allowlist_for(jurisdiction: str, tax_type: str = "vat") -> list[str]:
    """获取指定管辖地的工具白名单

    Returns:
        ["mcp__tax_agent_uk_vat__get_vat_obligations", ...]
    """
    registry = get_registry()
    adapter = registry.get(jurisdiction)
    tool_set = adapter.get_agent_tools(TaxType(tax_type))
    if tool_set is None:
        return []
    return tool_set.get_allowlist()


def get_all_allowlists() -> dict[str, list[str]]:
    """获取所有管辖地的工具白名单

    Returns:
        {"uk_vat": ["mcp__tax_agent_uk_vat__...", ...], ...}
    """
    registry = get_registry()
    result = {}
    for adapter in registry._adapters.values():
        for tax_type in adapter.tax_types:
            tool_set = adapter.get_agent_tools(tax_type)
            if tool_set is None:
                continue
            key = f"{adapter.country_code}_{tax_type.value}"
            result[key] = tool_set.get_allowlist()
    return result


# ═══════════════════════════════════════════════════════════
# Backward Compatibility
# ═══════════════════════════════════════════════════════════

# 旧版单一 MCP Server（为向后兼容保留，实际使用 create_mcp_servers）
def create_tax_mcp_server():
    """Deprecated: 使用 create_mcp_servers(registry) 替代"""
    try:
        registry = get_registry()
        servers = create_mcp_servers(registry)
        # 默认返回 UK VAT 的 server
        return servers.get(("uk", "vat"), {}).get("instance")
    except RuntimeError:
        return None


# 旧版工具白名单（为向后兼容保留）
TOOL_ALLOWLIST: list[str] = []
