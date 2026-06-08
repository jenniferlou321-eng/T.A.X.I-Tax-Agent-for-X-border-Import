# TaxAgent Global — Multi-Country Tax Filing Documentation

> **面向中国跨境企业**的智能税务申报平台  
> 支持国家：🇬🇧 英国（VAT） · 🇩🇪 德国（VAT） · 🇫🇷 法国（VAT） · 🇨🇳 中国（增值税 / 企业所得税）

本文档按 **国家** 分类，详细描述各管辖地的：
- 📋 报税流程（Filing Workflow）
- 📐 报税规则（Filing Rules）
- 🔌 API 集成详情（API Integration）
- 🧮 税务计算逻辑（Tax Calculation）

---

## 📑 目录

### 🇬🇧 United Kingdom 英国
- [UK 概览与监管](./jurisdictions/uk/README.md)
- [UK VAT 报税流程](./jurisdictions/uk/vat-workflow.md)
- [UK VAT 9-Box 规则与计算](./jurisdictions/uk/vat-rules.md)
- [HMRC OAuth 2.0 授权](./jurisdictions/uk/oauth.md)
- [HMRC 沙盒测试指南](./jurisdictions/uk/sandbox-testing.md)

### 🇩🇪 Deutschland 德国（规划中）
### 🇫🇷 France 法国（规划中）
### 🇨🇳 China 中国（规划中）

### 🏗️ 平台架构
- [系统架构总览](./architecture/overview.md)
- [Orchestrator 6 阶段管线](./architecture/pipeline.md)
- [扩展新国家指南](./architecture/adding-new-jurisdiction.md)

### 📊 状态总览

| 国家 | 状态 | 税种 | 渠道 | 测试 |
|------|------|------|------|------|
| 🇬🇧 UK | ✅ 完成 | VAT | API (HMRC) | 沙盒已验证 |
| 🇩🇪 DE | 📋 规划 | VAT | API (BZSt) | - |
| 🇫🇷 FR | 📋 规划 | VAT | API (DGFiP) | - |
| 🇨🇳 CN | 📋 规划 | 增值税/企所税 | Browser (电子税务局) | - |

---

## 🚀 快速开始

```bash
# 启动后端
cd tax_agent
python -m uvicorn server.main:app --host 0.0.0.0 --port 8765

# 启动前端
cd tax_agent/frontend
npm run dev
```

API 文档：http://localhost:8765/docs

---
