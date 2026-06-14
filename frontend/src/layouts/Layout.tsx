import { useState } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  HomeIcon,
  GlobeAltIcon,
  DocumentTextIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon,
  Bars3Icon,
  ShieldCheckIcon,
  SunIcon,
  MoonIcon,
  ComputerDesktopIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline'
import { useTheme } from '../hooks/useTheme'
import UpdateNotificationCenter from '../components/UpdateNotificationCenter'

const navItems = [
  { to: '/dashboard', label: '仪表盘', icon: HomeIcon },
  { to: '/jurisdictions', label: '管辖地', icon: GlobeAltIcon },
  { to: '/filings/new', label: '新建申报', icon: DocumentTextIcon },
  { to: '/agent', label: '智能助手', icon: CpuChipIcon, badge: 'AI' },
  { to: '/settings', label: '设置', icon: Cog6ToothIcon },
]

const themeIcons = {
  dark: MoonIcon,
  light: SunIcon,
  system: ComputerDesktopIcon,
}

const themeLabels: Record<string, string> = {
  dark: '深色',
  light: '浅色',
  system: '跟随系统',
}

function ThemeToggle() {
  const { theme, resolved, toggle } = useTheme()
  const Icon = themeIcons[theme as keyof typeof themeIcons] || MoonIcon

  return (
    <button
      onClick={toggle}
      className="relative p-2 text-fg-muted hover:text-fg hover:bg-bg-elevated rounded-md transition-colors duration-200"
      aria-label={`当前主题: ${themeLabels[theme] || theme}，点击切换`}
      title={`主题: ${themeLabels[theme] || theme} (${resolved})`}
    >
      <Icon className="w-5 h-5" />
    </button>
  )
}

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-glow-primary">
        <ShieldCheckIcon className="w-5 h-5 text-on-primary" />
      </div>
      <div>
        <h1 className="text-lg font-bold text-fg leading-tight tracking-tight">TaxAgent</h1>
        <p className="text-[11px] text-fg-dim leading-tight tracking-wide uppercase">Global</p>
      </div>
    </div>
  )
}

function Layout() {
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const isLogin = location.pathname === '/login'
  if (isLogin) return <Outlet />

  const pageTitle = (() => {
    if (location.pathname === '/dashboard') return '仪表盘'
    if (location.pathname === '/jurisdictions') return '管辖地管理'
    if (location.pathname === '/filings/new') return '新建申报'
    if (location.pathname.startsWith('/filings/')) return '申报详情'
    if (location.pathname === '/agent') return '智能助手'
    if (location.pathname === '/settings') return '设置'
    if (location.pathname.startsWith('/cases/')) return 'Case 数据预览'
    if (location.pathname === '/docs/jiahang-capability-matrix') return '平台能力差距矩阵'
    return ''
  })()

  return (
    <div className="flex min-h-screen bg-bg">
      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-bg-overlay backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 w-64 bg-bg-surface border-r border-border flex flex-col transition-transform duration-300 ease-out lg:translate-x-0 ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Logo */}
        <div className="p-5 border-b border-border">
          <Logo />
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-md text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-primary-muted text-primary shadow-sm'
                    : 'text-fg-muted hover:bg-bg-elevated hover:text-fg'
                }`
              }
            >
              <item.icon className="w-[18px] h-[18px] shrink-0" strokeWidth={2} />
              {item.label}
              {'badge' in item && item.badge && (
                <span className="ml-auto px-1.5 py-0.5 bg-accent/20 text-accent text-[10px] font-bold rounded">
                  {item.badge}
                </span>
              )}
              {item.to === '/filings/new' && !('badge' in item) && (
                <span className="ml-auto px-1.5 py-0.5 bg-primary/20 text-primary text-[10px] font-bold rounded">
                  NEW
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User & Logout */}
        <div className="p-3 border-t border-border space-y-1">
          <div className="flex items-center gap-3 px-3.5 py-2.5">
            <div className="w-8 h-8 rounded-full bg-accent-muted flex items-center justify-center shrink-0">
              <span className="text-xs font-semibold text-accent">U</span>
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-fg truncate">Demo User</p>
              <p className="text-xs text-fg-dim truncate">demo@example.com</p>
            </div>
          </div>
          <button className="flex items-center gap-3 px-3.5 py-2.5 w-full rounded-md text-sm text-fg-muted hover:bg-bg-elevated hover:text-fg transition-colors duration-200">
            <ArrowRightOnRectangleIcon className="w-[18px] h-[18px]" strokeWidth={2} />
            退出登录
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        {/* Header */}
        <header className="h-14 bg-bg-surface/80 backdrop-blur-md border-b border-border flex items-center justify-between px-4 lg:px-6 sticky top-0 z-30">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-2 -ml-2 text-fg-muted hover:text-fg hover:bg-bg-elevated rounded-md transition-colors"
              aria-label="打开菜单"
            >
              <Bars3Icon className="w-5 h-5" />
            </button>
            <h2 className="text-sm font-semibold text-fg">{pageTitle}</h2>
          </div>

          <div className="flex items-center gap-1">
            <ThemeToggle />
            <UpdateNotificationCenter />
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default Layout
