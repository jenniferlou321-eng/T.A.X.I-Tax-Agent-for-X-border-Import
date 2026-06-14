# TAXI 案例文档索引

> 本目录收录 T.A.X.I. 平台所有**业务案例文档**,作为平台功能完善的路线图素材与对外展示资产。

---

## 案例总览

| 案例 ID | 公司主体 | 视角 | 期间 | 业务笔数 | 状态 | 文档 |
|---|---|---|---|---:|---|---|
| `case-jiahang-uk-fy2023` | Jiahang UK Holdings Ltd. | UK 子公司 | FY2023 | 36 | ✅ **主线** | [jiahang-capability-matrix.md](./jiahang-capability-matrix.md) |
| `case-jiahang-cn-fy2023` | 江苏嘉汉国际贸易有限公司 | CN 母公司 | FY2023 | 62 | ✅ **主线** | [jiahang-capability-matrix.md](./jiahang-capability-matrix.md) |
| `cn-parent-uk-sub-q1-2026` | (TechFlow) | UK+CN 跨境 | 2026 Q1 | ~50 | 🟡 历史 | [cn-parent-uk-sub-q1-2026.md](./cn-parent-uk-sub-q1-2026.md) |

> 注:TechFlow 三案例(`case-x-uk-standard` / `case-a-uk-subsidiary` / `case-b-cn-parent`)正在被嘉汉案例替代,清扫计划见 [jiahang-capability-matrix.md §附录 A](./jiahang-capability-matrix.md#附录-a-未来-techflow-清扫清单本轮不动)。

---

## 核心交付物

- **能力差距矩阵** [jiahang-capability-matrix.md](./jiahang-capability-matrix.md) — 18 税种 × 平台支持状态,P0/P1/P2/P3 优先级
- **数据模型说明** [jiahang-data-model.md](./jiahang-data-model.md) — C1-xxx → erp_import.json 行的精确映射
- **历史案例** [cn-parent-uk-sub-q1-2026.md](./cn-parent-uk-sub-q1-2026.md) — TechFlow 旧案例(Q1 2026)

---

## 案例访问入口

### 前端 Dashboard

打开 T.A.X.I. → 仪表盘 → "快速演示场景"区域,可见 2 张嘉汉案例卡 + 1 张能力差距卡(跳到本目录文档)。

### 后端 API

```bash
# 列出所有 demo case
curl http://localhost:8765/api/erp/cases

# 加载嘉汉 UK FY2023 案例(36 笔)
curl http://localhost:8765/api/erp/cases/case-jiahang-uk-fy2023 | jq '.sales | length'

# 加载嘉汉 CN FY2023 案例(62 笔)
curl http://localhost:8765/api/erp/cases/case-jiahang-cn-fy2023 | jq '.sales | length'
```

### 数据文件位置

```
data/erp_samples/
├── case-jiahang-uk-fy2023/        ← UK 子公司 FY2023(36 笔)
│   ├── erp_import.json            ← Pydantic ImportResult 兼容
│   ├── tax_requirements.json      ← 报税要求(8 UK 税种)
│   ├── capability_status.json     ← 平台能力状态
│   ├── case_summary.json
│   └── README.md
├── case-jiahang-cn-fy2023/        ← CN 母公司 FY2023(62 笔)
│   ├── erp_import.json
│   ├── tax_requirements.json      ← 报税要求(10 CN 税种)
│   ├── capability_status.json
│   ├── case_summary.json
│   └── README.md
├── case-a-uk-subsidiary/          ← 历史:TechFlow UK
├── case-b-cn-parent/              ← 历史:TechFlow CN
└── case-x-uk-standard/            ← 历史:TechFlow 标准
```

---

## 案例驱动平台完善

每个案例的 18 税种申报需求都映射到平台的**功能 backlog**:

- **当前实现**(2/18):UK VAT ✅ + UK 股息 WHT ✅(0% 实际不报)
- **P0 优先**(3 个):UK CT、CN VAT、CN CIT — 见矩阵
- **P1 长尾**(6 个):UK PAYE、Import Duty、CN 城建税、CN 境外抵免、UK WHT(利息+特许权)、CN 个税
- **P2/P3**(5 个):Business Rates、房产税、印花税、Apprenticeship Levy、不动产租赁 / 物业管理

详细路线图与工作量估计见 [jiahang-capability-matrix.md §七 平台能力提升的 3 步走路径图](./jiahang-capability-matrix.md#七-平台能力提升的-3-步走路径图)。
