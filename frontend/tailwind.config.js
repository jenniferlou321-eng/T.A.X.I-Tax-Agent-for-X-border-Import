/** @type {import('tailwindcss').Config} */
//
// Tailwind v3 config for the T.A.X.I. design system.
//
// The source uses both Tailwind utility classes (e.g. `flex`, `p-3`,
// `min-h-screen`) AND custom design tokens that map to brand colors (e.g.
// `bg-bg`, `text-fg-muted`, `border-border`). We map those tokens to
// CSS-variable-backed color names so the design system stays single-sourced
// (a runtime theme switch just rewrites the CSS vars; no rebuild needed).
//
// Dark mode is opt-in via `html[data-theme="light"]` (anything not light is
// treated as dark, which is the project's default).
//
// The "shadow-glow-primary" / "shadow-glow-accent" utilities come from a
// custom box-shadow definition below — same trick as the colors.
//
// We deliberately do NOT use Tailwind v4's @theme syntax. v4 needs Node 20+
// and the build host has only Node 16.

export default {
  content: ['./index.html', './src/**/*.{ts,tsx,html}'],
  darkMode: ['class', ':root:not([data-theme="light"])'],
  theme: {
    extend: {
      colors: {
        // brand / semantic — all backed by CSS variables defined in index.css
        primary: 'var(--primary)',
        'primary-hover': 'var(--primary-hover)',
        'primary-muted': 'var(--primary-muted)',
        'on-primary': 'var(--on-primary)',

        secondary: 'var(--secondary)',
        'secondary-hover': 'var(--secondary-hover)',

        accent: 'var(--accent)',
        'accent-hover': 'var(--accent-hover)',
        'accent-muted': 'var(--accent-muted)',

        success: 'var(--success)',
        'success-muted': 'var(--success-muted)',
        warning: 'var(--warning)',
        'warning-muted': 'var(--warning-muted)',
        error: 'var(--error)',
        'error-muted': 'var(--error-muted)',
        info: 'var(--info)',
        'info-muted': 'var(--info-muted)',

        // surfaces & foreground
        bg: 'var(--bg)',
        'bg-surface': 'var(--bg-surface)',
        'bg-elevated': 'var(--bg-elevated)',
        fg: 'var(--fg)',
        'fg-muted': 'var(--fg-muted)',
        'fg-dim': 'var(--fg-dim)',
        'fg-inverse': 'var(--fg-inverse)',

        // borders
        border: 'var(--border)',
        'border-subtle': 'var(--border-subtle)',
        'border-strong': 'var(--border-strong)',
      },
      boxShadow: {
        sm: 'var(--shadow-sm-val)',
        md: 'var(--shadow-md-val)',
        lg: 'var(--shadow-lg-val)',
        xl: 'var(--shadow-xl-val)',
        'glow-primary': 'var(--shadow-glow-primary-val)',
        'glow-accent': 'var(--shadow-glow-accent-val)',
      },
      borderRadius: {
        sm: '6px',
        md: '10px',
        lg: '14px',
        xl: '20px',
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      transitionDuration: {
        fast: '150ms',
        normal: '200ms',
        slow: '300ms',
      },
      transitionTimingFunction: {
        out: 'cubic-bezier(0, 0, 0.2, 1)',
        'in-out': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
    },
  },
  // We don't use any Tailwind plugins for the design system.
  plugins: [],
}
