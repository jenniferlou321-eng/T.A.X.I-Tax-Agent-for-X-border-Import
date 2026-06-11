/**
 * Markdown — 安全地把助手文本渲染为带样式的 React 元素。
 *
 * 设计要点：
 * - 用 react-markdown 9（基于 micromark + rehype）做解析，默认转义 HTML，
 *   无需 dangerouslySetInnerHTML，避免 XSS。
 * - remark-gfm 开启 GFM：表格、任务列表、删除线、围栏代码块的语言提示。
 * - rehype-highlight 给围栏代码块加语法高亮（依赖 highlight.js / lowlight，
 *   CSS 主题在 index.css 顶部 import）。
 * - 不依赖 @tailwindcss/typography（项目没装），所有 markdown 子元素
 *   通过 `components` prop 直接套上项目的设计 token。
 * - 流式阶段直接信任 micromark 的容错（未闭合 ``` / ** 不会抛错），
 *   末尾的 streaming caret 仍在 bubble 外侧渲染。
 */
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import type { Components } from 'react-markdown'

interface MarkdownProps {
  content: string
  /** 标记是否正在流式输出 — 仅影响外层 data attr，不影响解析逻辑。 */
  streaming?: boolean
}

// 子元素类名集中维护：与项目语义 token 对齐。
const cls = {
  h1: 'text-base font-semibold text-fg mt-3 mb-1.5 first:mt-0',
  h2: 'text-[15px] font-semibold text-fg mt-3 mb-1 first:mt-0',
  h3: 'text-sm font-semibold text-fg mt-2.5 mb-1 first:mt-0',
  h4: 'text-sm font-semibold text-fg-dim mt-2 mb-0.5 first:mt-0',
  p: 'text-fg leading-relaxed my-2 first:mt-0 last:mb-0',
  ul: 'list-disc pl-5 my-2 space-y-0.5 marker:text-fg-dim',
  ol: 'list-decimal pl-5 my-2 space-y-0.5 marker:text-fg-dim',
  li: 'text-fg leading-relaxed',
  blockquote:
    'border-l-2 border-accent pl-3 my-2 text-fg-dim italic [&>p]:my-1',
  codeInline:
    'font-mono text-[0.9em] text-secondary bg-bg-elevated px-1 py-0.5 rounded',
  codeBlock:
    'block font-mono text-xs my-2 whitespace-pre',
  a: 'text-primary underline-offset-2 hover:underline',
  table: 'w-full text-sm my-2 border-collapse',
  th: 'text-left font-semibold text-fg border-b border-border py-1 px-2',
  td: 'text-fg-dim border-b border-border-subtle py-1 px-2',
  hr: 'border-border my-3',
  strong: 'font-semibold text-fg',
  em: 'italic text-fg',
}

const components: Components = {
  h1: ({ node: _n, ...p }) => <h1 className={cls.h1} {...p} />,
  h2: ({ node: _n, ...p }) => <h2 className={cls.h2} {...p} />,
  h3: ({ node: _n, ...p }) => <h3 className={cls.h3} {...p} />,
  h4: ({ node: _n, ...p }) => <h4 className={cls.h4} {...p} />,
  p: ({ node: _n, ...p }) => <p className={cls.p} {...p} />,
  ul: ({ node: _n, ...p }) => <ul className={cls.ul} {...p} />,
  ol: ({ node: _n, ...p }) => <ol className={cls.ol} {...p} />,
  li: ({ node: _n, ...p }) => <li className={cls.li} {...p} />,
  blockquote: ({ node: _n, ...p }) => (
    <blockquote className={cls.blockquote} {...p} />
  ),
  // 内联 code：react-markdown 用 `inline` 区分 inline vs block。
  code: ({ node: _n, className: codeClass, children, ...rest }) => {
    const isBlock = /language-/.test(codeClass || '')
    if (isBlock) {
      // 围栏代码块 — className 自带 language-xxx；rehype-highlight 已
      // 注入 <span class="hljs-...">，所以这里只套容器样式。
      return (
        <code className={cls.codeBlock} {...rest}>
          {children}
        </code>
      )
    }
    return <code className={cls.codeInline} {...rest}>{children}</code>
  },
  // pre 只在围栏代码块里出现；rehype-highlight 已在 code 元素上注入
  // hljs class（github-dark 主题自包含 background/color），这里只给容器
  // 加上 border / padding / 圆角，避免双重背景。
  pre: ({ node: _n, ...p }) => (
    <pre
      className="my-2 rounded-lg border border-border overflow-x-auto bg-bg-elevated/40 p-3 text-xs"
      {...p}
    />
  ),
  a: ({ node: _n, ...p }) => (
    <a
      className={cls.a}
      target="_blank"
      rel="noopener noreferrer"
      {...p}
    />
  ),
  table: ({ node: _n, ...p }) => <table className={cls.table} {...p} />,
  thead: ({ node: _n, ...p }) => <thead {...p} />,
  tbody: ({ node: _n, ...p }) => <tbody {...p} />,
  tr: ({ node: _n, ...p }) => <tr {...p} />,
  th: ({ node: _n, ...p }) => <th className={cls.th} {...p} />,
  td: ({ node: _n, ...p }) => <td className={cls.td} {...p} />,
  hr: ({ node: _n, ...p }) => <hr className={cls.hr} {...p} />,
  strong: ({ node: _n, ...p }) => <strong className={cls.strong} {...p} />,
  em: ({ node: _n, ...p }) => <em className={cls.em} {...p} />,
}

export default function Markdown({ content, streaming }: MarkdownProps) {
  return (
    <div
      className="markdown text-sm"
      data-streaming={streaming ? 'true' : undefined}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
