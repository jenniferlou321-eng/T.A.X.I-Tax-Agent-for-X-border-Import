import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ChevronDownIcon,
  ChevronUpIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CalculatorIcon,
} from '@heroicons/react/24/outline'
import { api } from '../api/client'
import { useDemoStore } from '../stores/demoStore'
import type { ImportResult, SalesTransaction, PurchaseTransaction } from '../types'
import type { JiahangTransactionExtension } from '../types/jiahang'
import CapabilityBadge from './jiahang/CapabilityBadge'

// 联合类型:基础 transaction + 嘉汉扩展字段
type JiahangSales = SalesTransaction & JiahangTransactionExtension
type JiahangPurchase = PurchaseTransaction & JiahangTransactionExtension

// 货币格式化(按行 currency 字段切换)
function formatAmount(value: string | number, currency?: string): string {
  const num = Number(value)
  if (isNaN(num)) return '—'
  const symbol = currency === 'CNY' ? '¥' : '£'
  return `${symbol}${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function InvoiceGroup({
  title,
  count,
  netTotal,
  vatTotal,
  currency,
  children,
}: {
  title: string
  count: number
  netTotal: number
  vatTotal: number
  currency: string
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(true)
  const symbol = currency === 'CNY' ? '¥' : '£'

  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-bg-elevated/50 hover:bg-bg-elevated transition-colors"
      >
        <div className="flex items-center gap-3">
          {open ? (
            <ChevronUpIcon className="w-4 h-4 text-fg-dim" />
          ) : (
            <ChevronDownIcon className="w-4 h-4 text-fg-dim" />
          )}
          <span className="font-medium text-fg text-sm">{title}</span>
          <span className="text-xs text-fg-dim bg-bg-elevated px-2 py-0.5 rounded-full">
            {count} 张
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs text-fg-dim">
          <span>
            净额{' '}
            <span className="font-mono text-fg">
              {symbol}
              {netTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </span>
          <span>
            VAT{' '}
            <span className="font-mono text-fg">
              {symbol}
              {vatTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </span>
        </div>
      </button>
      {open && children}
    </div>
  )
}

function InvoiceTable({
  invoices,
  kind,
}: {
  invoices: JiahangSales[] | JiahangPurchase[]
  kind: 'sales' | 'purchases'
}) {
  return (
    <div className="max-h-96 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="bg-bg sticky top-0">
          <tr className="text-xs text-fg-dim">
            <th className="px-3 py-2 text-left whitespace-nowrap">ID</th>
            <th className="px-3 py-2 text-left whitespace-nowrap">日期</th>
            <th className="px-3 py-2 text-left">对方</th>
            <th className="px-3 py-2 text-left whitespace-nowrap">业务类型</th>
            <th className="px-3 py-2 text-left whitespace-nowrap">税码</th>
            <th className="px-3 py-2 text-right whitespace-nowrap">净额</th>
            <th className="px-3 py-2 text-right whitespace-nowrap">VAT</th>
            <th className="px-3 py-2 text-right whitespace-nowrap">总额</th>
            <th className="px-3 py-2 text-left whitespace-nowrap">平台状态</th>
            <th className="px-3 py-2 text-left whitespace-nowrap">关联方</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv) => {
            const currency = inv.currency
            const isJiahang = !!inv.txn_type || !!inv.platform_status
            return (
              <tr
                key={inv.id}
                className={`border-t border-border hover:bg-bg-elevated/40 transition-colors ${
                  isJiahang ? '' : 'text-fg-muted'
                }`}
                title={inv.notes || ''}
              >
                <td className="px-3 py-2 font-mono text-xs text-fg whitespace-nowrap">
                  {inv.id}
                </td>
                <td className="px-3 py-2 text-fg-dim whitespace-nowrap text-xs">
                  {inv.txn_date}
                </td>
                <td className="px-3 py-2 text-fg">{inv.counterparty}</td>
                <td className="px-3 py-2 text-xs text-fg-dim">
                  {inv.txn_type ? (
                    <span className="font-mono text-[11px]">{inv.txn_type}</span>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="px-3 py-2 text-xs text-fg-dim">
                  {inv.tax_code ? (
                    <span className="font-mono text-[11px]">{inv.tax_code}</span>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  {formatAmount(inv.net_amount, currency)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  {formatAmount(inv.vat_amount, currency)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  {formatAmount(inv.gross_amount, currency)}
                </td>
                <td className="px-3 py-2">
                  <CapabilityBadge status={inv.platform_status} />
                </td>
                <td className="px-3 py-2 text-xs text-fg-dim">
                  {inv.related_party_id ? (
                    <span className="font-mono text-[11px] text-primary">
                      {inv.related_party_id}
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function ErpInvoiceTable() {
  const buffer = useDemoStore((s) => s.buffer)
  const setErpData = useDemoStore((s) => s.setErpData)
  // 用 preset.erpCaseId 作为后端 case 目录名(替代原来的 presetId 直传)
  const presetId = buffer?.presetId ?? ''
  const erpCaseId = buffer?.preset?.erpCaseId ?? presetId

  const {
    data: importResult,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['erp', 'case', erpCaseId],
    queryFn: () => api.erp.getCase(erpCaseId),
    enabled: !!erpCaseId && !buffer?.erpData,
    staleTime: Infinity,
  })

  // 懒加载成功后写回 buffer
  if (importResult && !buffer?.erpData) {
    setErpData(importResult)
  }

  const data: ImportResult | null = buffer?.erpData ?? importResult ?? null

  const sales = (data?.sales ?? []) as unknown as JiahangSales[]
  const purchases = (data?.purchases ?? []) as unknown as JiahangPurchase[]

  // 货币判断:从 metadata.currency 或第一行的 currency,默认 GBP
  const dataCurrency: 'GBP' | 'CNY' =
    (data?.metadata?.currency as 'GBP' | 'CNY' | undefined) ??
    (sales[0]?.currency ?? purchases[0]?.currency ?? 'GBP')

  const salesNet = sales.reduce((s, i) => s + Number(i.net_amount), 0)
  const salesVat = sales.reduce((s, i) => s + Number(i.vat_amount), 0)
  const purchasesNet = purchases.reduce((s, i) => s + Number(i.net_amount), 0)
  const purchasesVat = purchases.reduce(
    (s, i) => s + Number(i.vat_amount),
    0,
  )

  if (isLoading && !data) {
    return (
      <div className="card p-8 flex flex-col items-center justify-center gap-3 text-fg-dim">
        <ArrowPathIcon className="w-6 h-6 animate-spin" />
        <p className="text-sm">正在加载 ERP 原始数据...</p>
      </div>
    )
  }

  if (isError && !data) {
    return (
      <div className="card p-6 border-error/30">
        <div className="flex items-center gap-2 mb-3">
          <ExclamationTriangleIcon className="w-5 h-5 text-error" />
          <p className="text-sm font-semibold text-error">加载失败</p>
        </div>
        <p className="text-sm text-fg-muted mb-4">
          {(error as Error)?.message || '无法加载 ERP 数据'}
        </p>
        <button onClick={() => refetch()} className="btn btn-secondary btn-sm">
          <ArrowPathIcon className="w-4 h-4" />
          重试
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <CalculatorIcon className="w-4 h-4 text-fg-muted" />
        <h2 className="text-base font-semibold text-fg">ERP 原始业务数据</h2>
        {data && (
          <>
            <span className="text-xs text-fg-dim">
              来源: {data.source_filename || data.source_profile}
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-bg-elevated text-[11px] font-mono text-fg-muted">
              货币: {dataCurrency}
            </span>
            {data?.metadata?.fiscal_year && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-bg-elevated text-[11px] font-mono text-fg-muted">
                {data.metadata.fiscal_year}
              </span>
            )}
          </>
        )}
      </div>

      {sales.length === 0 && purchases.length === 0 ? (
        <div className="card p-6 text-center text-fg-dim text-sm">
          该 case 暂无发票数据
        </div>
      ) : (
        <div className="space-y-3">
          <InvoiceGroup
            title="销售发票"
            count={sales.length}
            netTotal={salesNet}
            vatTotal={salesVat}
            currency={dataCurrency}
          >
            <InvoiceTable invoices={sales} kind="sales" />
          </InvoiceGroup>

          <InvoiceGroup
            title="采购发票"
            count={purchases.length}
            netTotal={purchasesNet}
            vatTotal={purchasesVat}
            currency={dataCurrency}
          >
            <InvoiceTable invoices={purchases} kind="purchases" />
          </InvoiceGroup>
        </div>
      )}
    </div>
  )
}
