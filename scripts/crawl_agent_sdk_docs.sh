#!/usr/bin/env bash
# Crawl https://code.claude.com/docs/en/agent-sdk/*  →  markdown per page
# Output:
#   docs/superpowers/reference/code-claude-com/agent-sdk/raw/<slug>.html  (full SSR HTML)
#   docs/superpowers/reference/code-claude-com/agent-sdk/markdown/<slug>.md (extracted main content)
#   docs/superpowers/reference/code-claude-com/agent-sdk/INDEX.md          (manifest)
set -euo pipefail

BASE="https://code.claude.com"
SECTION="/docs/en/agent-sdk"
OUT="/root/TAXI/docs/superpowers/reference/code-claude-com/agent-sdk"
RAW="$OUT/raw"
MD="$OUT/markdown"
mkdir -p "$RAW" "$MD"

# 1) Pull a seed page to discover the link set
curl -sS -L --max-time 30 -A "Mozilla/5.0" "$BASE$SECTION/overview" -o "$RAW/_seed.html"

# Extract all /docs/en/agent-sdk/* hrefs
mapfile -t PAGES < <(
  grep -oE 'href="/docs/en/agent-sdk/[^"#?]*"' "$RAW/_seed.html" \
    | sed 's/href="//;s/"$//' \
    | sort -u
)

echo "Found ${#PAGES[@]} unique pages under $SECTION"

# 2) Download each page
for path in "${PAGES[@]}"; do
  slug="${path##*/}"
  slug="${slug:-overview}"
  if false; then
    echo "  [skip] $slug (already downloaded)"
    continue
  fi
  echo "  [fetch] $slug  ($BASE$path)"
  curl -sS -L --max-time 30 -A "Mozilla/5.0" "$BASE$path" -o "$RAW/$slug.html" || {
    echo "  [FAIL ] $slug"
    continue
  }
done

# 3) Extract main content → markdown-ish plain text
# Strategy: grep the article body region. Mintlify Next.js wraps content in
# <article> or <main>. We extract everything between <main ...> and </main>,
# then strip tags, decode entities, and emit as a simple markdown-ish text.
python3 - "$RAW" "$MD" "$BASE" "$SECTION" <<'PYEOF'
import os, re, html, sys
from html.parser import HTMLParser
from pathlib import Path

RAW = Path(sys.argv[1])
MD  = Path(sys.argv[2])
BASE = sys.argv[3]
SECTION = sys.argv[4]

class TextExtract(HTMLParser):
    BLOCK = {"p","h1","h2","h3","h4","h5","h6","li","pre","code","div","section","article","br","tr"}
    SKIP  = {"script","style","nav","footer","header","aside","svg","noscript"}
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0
        self.in_main = 0
        self.in_pre = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip_depth += 1
            return
        if tag in ("main","article"):
            self.in_main += 1
        if self.skip_depth:
            return
        if tag == "pre":
            self.in_pre += 1
            self.parts.append("\n```\n")
            return
        if tag == "code" and not self.in_pre:
            self.parts.append("`")
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag in ("h1","h2","h3","h4","h5","h6"):
            self.parts.append(f"\n\n{'#' * int(tag[1])} ")
        if tag == "li":
            self.parts.append("\n- ")
    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip_depth = max(0, self.skip_depth-1)
            return
        if tag in ("main","article") and self.in_main:
            self.in_main -= 1
        if self.skip_depth:
            return
        if tag == "pre":
            self.in_pre = max(0, self.in_pre-1)
            self.parts.append("\n```\n")
            return
        if tag == "code" and not self.in_pre:
            self.parts.append("`")
    def handle_data(self, data):
        if self.skip_depth or not self.in_main:
            return
        self.parts.append(data)

for html_path in sorted(RAW.glob("*.html")):
    if html_path.name == "_seed.html":
        continue
    slug = html_path.stem
    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    # extract title
    m = re.search(r"<title>(.*?)</title>", raw, re.S|re.I)
    title = html.unescape(m.group(1)).strip() if m else slug
    p = TextExtract()
    try:
        p.feed(raw)
    except Exception as e:
        print(f"  [parse err] {slug}: {e}")
        continue
    text = "".join(p.parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = html.unescape(text)
    out = MD / f"{slug}.md"
    out.write_text(f"# {title}\n\n_source: {SECTION}/{slug}_\n\n{text.strip()}\n", encoding="utf-8")
    print(f"  [md] {slug}.md  ({len(text)} chars)")
PYEOF
BASE_URL="https://code.claude.com"

# 4) Write INDEX manifest
{
  echo "# Claude Agent SDK — Documentation Mirror"
  echo ""
  echo "Source: https://code.claude.com/docs/en/agent-sdk"
  echo "Captured: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo ""
  echo "## Pages (${#PAGES[@]})"
  echo ""
  for path in "${PAGES[@]}"; do
    slug="${path##*/}"
    slug="${slug:-overview}"
    [ -f "$MD/$slug.md" ] || continue
    title=$(grep -m1 '^# ' "$MD/$slug.md" | sed 's/^# //')
    bytes=$(stat -c %s "$MD/$slug.md")
    echo "- [$title](markdown/${slug}.md) — ${bytes} bytes — ${BASE}${path}"
  done
} > "$OUT/INDEX.md"

echo ""
echo "Done. INDEX:"
cat "$OUT/INDEX.md"
