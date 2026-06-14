import { useState, useEffect } from 'react'
import {
  UserIcon,
  BuildingOfficeIcon,
  BellIcon,
  ShieldCheckIcon,
  CheckIcon,
  KeyIcon,
  LinkIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'
import { api } from '../api/client'
import { useUserProfile } from '../stores/userProfile'

function SettingsPage() {
  const [activeTab, setActiveTab] = useState('profile')
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const tabs = [
    { id: 'profile', label: '纳税人信息', icon: UserIcon },
    { id: 'company', label: '企业信息', icon: BuildingOfficeIcon },
    { id: 'notifications', label: '通知偏好', icon: BellIcon },
    { id: 'security', label: '安全设置', icon: ShieldCheckIcon },
    { id: 'corpus', label: '知识库同步', icon: ArrowPathIcon },
  ]

  return (
    <div className="max-w-4xl mx-auto space-y-6 fade-in">
      <div>
        <h1 className="text-2xl font-bold text-fg tracking-tight">设置</h1>
        <p className="text-sm text-fg-muted mt-1">管理您的账户信息和平台偏好</p>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Sidebar Tabs */}
        <div className="w-full lg:w-52 shrink-0">
          <div className="card overflow-hidden">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 text-sm font-medium transition-all duration-200 ${
                  activeTab === tab.id
                    ? 'bg-primary-muted text-primary border-l-2 border-primary'
                    : 'text-fg-muted hover:bg-bg-elevated hover:text-fg border-l-2 border-transparent'
                }`}
              >
                <tab.icon className="w-[18px] h-[18px] shrink-0" strokeWidth={2} />
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 card p-6 min-h-[400px]">
          {activeTab === 'profile' && <ProfileSettings onSave={handleSave} saved={saved} />}
          {activeTab === 'company' && <CompanySettings onSave={handleSave} saved={saved} />}
          {activeTab === 'notifications' && <NotificationSettings onSave={handleSave} saved={saved} />}
          {activeTab === 'security' && <SecuritySettings />}
          {activeTab === 'corpus' && <CorpusSyncPanel />}
        </div>
      </div>
    </div>
  )
}

function SaveButton({ onSave, saved }: { onSave: () => void; saved: boolean }) {
  return (
    <div className="flex items-center gap-3 pt-2">
      {saved && (
        <span className="text-sm text-success flex items-center gap-1 fade-in">
          <CheckIcon className="w-4 h-4" />
          已保存
        </span>
      )}
      <button
        onClick={onSave}
        className="btn btn-primary ml-auto"
      >
        保存修改
      </button>
    </div>
  )
}

function ProfileSettings({ onSave, saved }: { onSave: () => void; saved: boolean }) {
  const taxpayer = useUserProfile((s) => s.taxpayer)
  const setTaxpayer = useUserProfile((s) => s.setTaxpayer)

  return (
    <div className="space-y-5 fade-in">
      <h2 className="text-lg font-semibold text-fg">纳税人信息</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-fg mb-1.5">纳税人名称</label>
          <input
            type="text"
            value={taxpayer.name}
            onChange={(e) => setTaxpayer({ name: e.target.value })}
            placeholder="企业/个人名称"
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-fg mb-1.5">
            税务编号 (VRN)
            <span className="text-xs text-fg-dim font-normal ml-1.5">
              · 新建申报时自动填入
            </span>
          </label>
          <input
            type="text"
            value={taxpayer.vrn}
            onChange={(e) => setTaxpayer({ vrn: e.target.value.trim() })}
            placeholder="GB123456789"
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-fg mb-1.5">联系邮箱</label>
          <input
            type="email"
            value={taxpayer.email}
            onChange={(e) => setTaxpayer({ email: e.target.value })}
            placeholder="contact@example.com"
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-fg mb-1.5">联系电话</label>
          <input
            type="tel"
            value={taxpayer.phone}
            onChange={(e) => setTaxpayer({ phone: e.target.value })}
            placeholder="+44 20 1234 5678"
            className="input"
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-fg mb-1.5">注册地址</label>
        <textarea
          rows={3}
          value={taxpayer.address}
          onChange={(e) => setTaxpayer({ address: e.target.value })}
          placeholder="详细地址..."
          className="input resize-none"
        />
      </div>
      <SaveButton onSave={onSave} saved={saved} />
    </div>
  )
}

function CompanySettings({ onSave, saved }: { onSave: () => void; saved: boolean }) {
  return (
    <div className="space-y-5 fade-in">
      <h2 className="text-lg font-semibold text-fg">企业信息</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-fg mb-1.5">公司注册号</label>
          <input type="text" placeholder="12345678" className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-fg mb-1.5">公司类型</label>
          <div className="relative">
            <select className="input appearance-none pr-10">
              <option>Limited Company</option>
              <option>Sole Trader</option>
              <option>Partnership</option>
            </select>
          </div>
        </div>
      </div>
      <SaveButton onSave={onSave} saved={saved} />
    </div>
  )
}

function NotificationSettings({ onSave, saved }: { onSave: () => void; saved: boolean }) {
  return (
    <div className="space-y-5 fade-in">
      <h2 className="text-lg font-semibold text-fg">通知偏好</h2>
      <div className="space-y-1">
        {[
          { label: '申报成功通知', desc: '当申报被税务机关受理时发送邮件通知', checked: true },
          { label: '申报失败提醒', desc: '当申报被驳回或出现错误时立即通知', checked: true },
          { label: '申报截止日期提醒', desc: '在申报截止日期前 7 天、3 天、1 天发送提醒', checked: true },
          { label: '税务政策更新', desc: '当管辖地税法或申报规则发生变化时通知', checked: false },
        ].map((item) => (
          <div
            key={item.label}
            className="flex items-start justify-between py-4 px-3 -mx-3 rounded-lg hover:bg-bg-elevated/30 transition-colors"
          >
            <div className="pr-4">
              <p className="text-sm font-medium text-fg">{item.label}</p>
              <p className="text-xs text-fg-muted mt-0.5">{item.desc}</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer shrink-0 mt-0.5">
              <input type="checkbox" defaultChecked={item.checked} className="sr-only peer" />
              <div className="w-11 h-6 bg-fg-dim/30 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:shadow-sm after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary" />
            </label>
          </div>
        ))}
      </div>
      <SaveButton onSave={onSave} saved={saved} />
    </div>
  )
}

function SecuritySettings() {
  const [authStatus, setAuthStatus] = useState<'idle' | 'connecting' | 'code_input' | 'exchanging' | 'connected' | 'error'>('idle')
  const [_authUrl, setAuthUrl] = useState('')
  const [authCode, setAuthCode] = useState('')
  const [authError, setAuthError] = useState('')
  const [isConnected, setIsConnected] = useState(false)
  const [expiresAt, setExpiresAt] = useState<string | null>(null)

  // 检查当前认证状态
  useEffect(() => {
    api.channel.authStatus('uk', 'vat')
      .then((res) => {
        setIsConnected(res.authenticated)
        if (res.expires_at) {
          setExpiresAt(new Date(res.expires_at * 1000).toLocaleString('zh-CN'))
        }
      })
      .catch(() => setIsConnected(false))
  }, [])

  const handleConnect = async () => {
    setAuthStatus('connecting')
    setAuthError('')
    try {
      const res = await api.channel.authUrl('uk', 'vat')
      setAuthUrl(res.auth_url)
      setAuthStatus('code_input')
      // 打开授权页面
      window.open(res.auth_url, '_blank', 'width=800,height=700')
    } catch (e: any) {
      setAuthError(e.message || '获取授权链接失败')
      setAuthStatus('error')
    }
  }

  const handleExchangeCode = async () => {
    if (!authCode.trim()) return
    setAuthStatus('exchanging')
    setAuthError('')
    try {
      const res = await api.channel.callback('uk', 'vat', authCode.trim())
      if (res.success) {
        setIsConnected(true)
        setAuthStatus('connected')
        if (res.expires_at) {
          setExpiresAt(new Date(res.expires_at).toLocaleString('zh-CN'))
        }
      } else {
        setAuthError(res.error || '授权失败')
        setAuthStatus('error')
      }
    } catch (e: any) {
      setAuthError(e.message || '交换 Token 失败')
      setAuthStatus('error')
    }
  }

  return (
    <div className="space-y-5 fade-in">
      <h2 className="text-lg font-semibold text-fg">安全设置</h2>

      <div className="space-y-3">
        {/* HMRC OAuth */}
        <div className="card p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isConnected ? 'bg-success-muted' : 'bg-bg-elevated'}`}>
                <LinkIcon className={`w-5 h-5 ${isConnected ? 'text-success' : 'text-fg-muted'}`} />
              </div>
              <div>
                <p className="text-sm font-medium text-fg">HMRC OAuth 授权</p>
                <p className="text-xs text-fg-muted mt-0.5">
                  {isConnected
                    ? `已连接${expiresAt ? ` · Token 过期: ${expiresAt}` : ''}`
                    : '未连接 — 需要授权才能提交 VAT 申报'}
                </p>
              </div>
            </div>
            {isConnected ? (
              <span className="badge bg-success-muted text-success border-success/20">
                <CheckIcon className="w-3 h-3" />
                已连接
              </span>
            ) : (
              <button
                onClick={handleConnect}
                disabled={authStatus === 'connecting'}
                className="btn btn-primary text-sm px-4 py-2"
              >
                {authStatus === 'connecting' ? (
                  <>
                    <ArrowPathIcon className="w-4 h-4 animate-spin" />
                    获取中...
                  </>
                ) : (
                  <>
                    <LinkIcon className="w-4 h-4" />
                    连接 HMRC
                  </>
                )}
              </button>
            )}
          </div>

          {/* Code 输入区 */}
          {(authStatus === 'code_input' || authStatus === 'exchanging' || authStatus === 'error') && !isConnected && (
            <div className="mt-4 pt-4 border-t border-border space-y-3">
              <p className="text-sm text-fg-muted">
                请在弹出的 HMRC 页面完成授权，然后将页面显示的 Authorization Code 粘贴到下方：
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={authCode}
                  onChange={(e) => setAuthCode(e.target.value)}
                  placeholder="粘贴 Authorization Code"
                  className="input flex-1"
                  disabled={authStatus === 'exchanging'}
                />
                <button
                  onClick={handleExchangeCode}
                  disabled={!authCode.trim() || authStatus === 'exchanging'}
                  className="btn btn-primary"
                >
                  {authStatus === 'exchanging' ? (
                    <ArrowPathIcon className="w-4 h-4 animate-spin" />
                  ) : (
                    '确认授权'
                  )}
                </button>
              </div>
              {authError && (
                <div className="p-3 bg-error-muted border border-error/20 rounded-lg flex items-start gap-2">
                  <ExclamationTriangleIcon className="w-4 h-4 text-error mt-0.5 shrink-0" />
                  <p className="text-sm text-error">{authError}</p>
                </div>
              )}
            </div>
          )}

          {isConnected && (
            <div className="mt-4 pt-4 border-t border-border">
              <div className="p-3 bg-success-muted/50 border border-success/20 rounded-lg">
                <p className="text-sm text-success">
                  ✅ 已成功连接 HMRC。您可以进行 VAT 申报义务查询和提交 VAT Return。
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="card p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-bg-elevated flex items-center justify-center">
              <KeyIcon className="w-5 h-5 text-fg-muted" />
            </div>
            <div>
              <p className="text-sm font-medium text-fg">修改密码</p>
              <p className="text-xs text-fg-muted mt-0.5">上次修改: 2026-05-30</p>
            </div>
          </div>
          <button className="btn btn-secondary text-sm px-4 py-2">
            修改
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Knowledge Base Sync Panel ──────────────────────────────────

type SourceEntry = {
  source_id: string
  title: string
  url: string
  source_authority: string
  tax_tags: string[]
  chunk_count: number
  status: string
}

type DiffReportShape = {
  summary: { new_count: number; modified_count: number }
  new: SourceEntry[]
  modified: SourceEntry[]
}

function CorpusSyncPanel() {
  const [status, setStatus] = useState<'idle' | 'checking' | 'applying'>('idle')
  const [diffReport, setDiffReport] = useState<DiffReportShape | null>(null)
  const [applyResult, setApplyResult] = useState<{ new_count: number; modified_count: number; total_chunks: number } | null>(null)
  const [noMirror, setNoMirror] = useState(false)
  const [error, setError] = useState('')
  const [partialMessage, setPartialMessage] = useState('')

  const handleCheck = async () => {
    setStatus('checking')
    setError('')
    setNoMirror(false)
    setDiffReport(null)
    setApplyResult(null)
    setPartialMessage('')
    try {
      const res = await api.corpus.checkUpdates()
      if (res.status === 'no_mirror') {
        setNoMirror(true)
        setStatus('idle')
      } else if (res.status === 'ok' && res.report) {
        setDiffReport(res.report)
        setStatus('idle')
      } else {
        setError(res.message || '检查更新失败')
        setStatus('idle')
      }
    } catch (e: any) {
      setError(e.message || '检查更新失败')
      setStatus('idle')
    }
  }

  const handleApply = async () => {
    setStatus('applying')
    setError('')
    setPartialMessage('')
    try {
      const res = await api.corpus.applyUpdates()
      if ((res.status === 'ok' || res.status === 'partial') && res.result) {
        setApplyResult(res.result)
        setDiffReport(null)
        if (res.status === 'partial') {
          setPartialMessage(res.message || '部分成功')
        }
        setStatus('idle')
      } else {
        setError(res.message || '应用更新失败')
        setStatus('idle')
      }
    } catch (e: any) {
      setError(e.message || '应用更新失败')
      setStatus('idle')
    }
  }

  const hasChanges =
    diffReport &&
    (diffReport.summary.new_count > 0 || diffReport.summary.modified_count > 0)

  const renderSourceList = (entries: SourceEntry[], label: string, color: string) => {
    if (entries.length === 0) return null
    const shown = entries.slice(0, 20)
    const hidden = entries.length - shown.length
    return (
      <div>
        <h4 className="text-sm font-medium text-fg mb-2">
          {label} ({entries.length})
        </h4>
        <div className="max-h-60 overflow-y-auto space-y-1">
          {shown.map((s) => (
            <div
              key={s.source_id}
              className="text-xs text-fg-muted py-1.5 px-2 bg-bg-elevated rounded truncate"
              title={s.url || s.source_id}
            >
              {s.chunk_count > 1 && (
                <span className={`${color} font-medium mr-1.5`}>
                  [{s.chunk_count} chunks]
                </span>
              )}
              {s.title || s.source_id}
            </div>
          ))}
          {hidden > 0 && (
            <p className="text-xs text-fg-dim px-2 py-1">… 还有 {hidden} 个</p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5 fade-in">
      <h2 className="text-lg font-semibold text-fg">知识库同步</h2>
      <p className="text-sm text-fg-muted leading-relaxed">
        模拟"上游官网（如 HMRC / GOV.UK）发布新内容"的场景：
        将新的 <code className="text-xs bg-bg-elevated px-1.5 py-0.5 rounded">chunks_with_tags.jsonl</code> 放入
        <code className="text-xs bg-bg-elevated px-1.5 py-0.5 rounded ml-1">data/tax_corpus_mirror/</code> 目录，
        然后点击下方按钮对比差异并增量合并到本地知识库。
      </p>

      {/* 操作按钮 */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleCheck}
          disabled={status !== 'idle'}
          className="btn btn-primary"
        >
          {status === 'checking' ? (
            <>
              <ArrowPathIcon className="w-4 h-4 animate-spin" />
              检查中...
            </>
          ) : (
            <>
              <ArrowPathIcon className="w-4 h-4" />
              检查更新
            </>
          )}
        </button>
      </div>

      {/* 无镜像提示 */}
      {noMirror && (
        <div className="card p-4 bg-warning-muted/30 border border-warning/20">
          <p className="text-sm text-warning">
            未找到镜像文件。请将 <code className="text-xs bg-bg-elevated px-1.5 py-0.5 rounded">chunks_with_tags.jsonl</code> 放入
            <code className="text-xs bg-bg-elevated px-1.5 py-0.5 rounded ml-1">data/tax_corpus_mirror/</code> 目录后再试。
          </p>
        </div>
      )}

      {/* 错误 */}
      {error && (
        <div className="card p-4 bg-error-muted/30 border border-error/20">
          <p className="text-sm text-error">❌ {error}</p>
        </div>
      )}

      {/* 差异报告 */}
      {diffReport && (
        <div className="card p-4 space-y-4">
          <div>
            <h3 className="text-base font-semibold text-fg">差异摘要</h3>
            <div className="flex gap-3 mt-2 flex-wrap">
              <div className="px-3 py-2 bg-info-muted/30 rounded-lg">
                <span className="text-sm text-info font-medium">
                  新增: {diffReport.summary.new_count} 个来源
                </span>
              </div>
              <div className="px-3 py-2 bg-warning-muted/30 rounded-lg">
                <span className="text-sm text-warning font-medium">
                  修改: {diffReport.summary.modified_count} 个来源
                </span>
              </div>
            </div>
          </div>

          {renderSourceList(diffReport.new, '新增来源', 'text-info')}
          {renderSourceList(diffReport.modified, '修改来源', 'text-warning')}

          {hasChanges && (
            <button
              onClick={handleApply}
              disabled={status !== 'idle'}
              className="btn btn-primary"
            >
              {status === 'applying' ? (
                <>
                  <ArrowPathIcon className="w-4 h-4 animate-spin" />
                  应用中...
                </>
              ) : (
                <>
                  <CheckIcon className="w-4 h-4" />
                  应用更新
                </>
              )}
            </button>
          )}

          {!hasChanges && (
            <div className="card p-3 bg-success-muted/30 border border-success/20">
              <p className="text-sm text-success">
                ✅ 知识库已是最新,没有需要更新的内容。
              </p>
            </div>
          )}
        </div>
      )}

      {/* 应用结果 */}
      {applyResult && (
        <div className="card p-4 bg-success-muted/30 border border-success/20 space-y-2">
          <p className="text-sm text-success font-medium">✅ 更新已应用</p>
          <div className="text-xs text-fg-muted space-y-0.5">
            <p>新增: {applyResult.new_count} 个来源</p>
            <p>修改: {applyResult.modified_count} 个来源</p>
            <p>当前总 chunks: {applyResult.total_chunks}</p>
          </div>
          {partialMessage && (
            <p className="text-xs text-warning mt-2">⚠️ {partialMessage}</p>
          )}
        </div>
      )}
    </div>
  )
}

export default SettingsPage
