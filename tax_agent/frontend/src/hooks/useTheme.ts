import { useState, useEffect, useCallback } from 'react'

type Theme = 'dark' | 'light' | 'system'

const STORAGE_KEY = 'taxagent-theme'

function getSystemTheme(): 'dark' | 'light' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function getResolvedTheme(theme: Theme): 'dark' | 'light' {
  if (theme === 'system') return getSystemTheme()
  return theme
}

function applyTheme(resolved: 'dark' | 'light') {
  const html = document.documentElement
  if (resolved === 'light') {
    html.setAttribute('data-theme', 'light')
  } else {
    html.removeAttribute('data-theme')
  }
}

function getStoredTheme(): Theme {
  try {
    const raw = localStorage.getItem(STORAGE_KEY) as Theme | null
    if (raw === 'dark' || raw === 'light' || raw === 'system') return raw
  } catch { /* ignore */ }
  return 'system'
}

function setStoredTheme(theme: Theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch { /* ignore */ }
}

// Initialize theme before React renders (called in main.tsx)
export function initTheme() {
  const theme = getStoredTheme()
  const resolved = getResolvedTheme(theme)
  applyTheme(resolved)
  return theme
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => getStoredTheme())
  const [resolved, setResolved] = useState<'dark' | 'light'>(
    () => getResolvedTheme(getStoredTheme())
  )

  useEffect(() => {
    const resolvedNow = getResolvedTheme(theme)
    setResolved(resolvedNow)
    applyTheme(resolvedNow)
    setStoredTheme(theme)
  }, [theme])

  // Listen to system preference changes when in "system" mode
  useEffect(() => {
    if (theme !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (e: MediaQueryListEvent) => {
      const resolvedNow = e.matches ? 'dark' : 'light'
      setResolved(resolvedNow)
      applyTheme(resolvedNow)
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme])

  const toggle = useCallback(() => {
    setThemeState((prev) => {
      if (prev === 'dark') return 'light'
      if (prev === 'light') return 'system'
      return 'dark'
    })
  }, [])

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t)
  }, [])

  return { theme, resolved, toggle, setTheme }
}
