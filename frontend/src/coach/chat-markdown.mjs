// The small slice of markdown the coach writes (bold, italics, code, headings, lists),
// parsed into plain data so the drawer renders it with Vue templates instead of v-html.

const INLINE = /(\*\*[^*\n]+?\*\*|__[^_\n]+?__|`[^`\n]+?`|\*[^*\s][^*\n]*?\*)/g

// "Ride **hard** today" → [{ text: 'Ride ' }, { text: 'hard', bold: true }, { text: ' today' }]
export const parseInline = (text) => {
  const spans = []
  let last = 0
  for (const match of String(text || '').matchAll(INLINE)) {
    if (match.index > last) spans.push({ text: text.slice(last, match.index) })
    const token = match[0]
    if (token.startsWith('**') || token.startsWith('__')) spans.push({ text: token.slice(2, -2), bold: true })
    else if (token.startsWith('`')) spans.push({ text: token.slice(1, -1), code: true })
    else spans.push({ text: token.slice(1, -1), italic: true })
    last = match.index + token.length
  }
  if (last < String(text || '').length) spans.push({ text: text.slice(last) })
  return spans
}

const BULLET = /^\s*(?:[-*•])\s+(.*)$/
const NUMBERED = /^\s*(\d+)[.)]\s+(.*)$/
const HASH_HEADING = /^\s*#{1,6}\s+(.*?)\s*#*\s*$/
// A line that is only bold text ("**What I'd do**") reads as a heading.
const BOLD_HEADING = /^\s*(?:\*\*|__)([^*_\n]+?)(?:\*\*|__)\s*:?\s*$/

// Message text → blocks: { type: 'heading' | 'paragraph', spans } or { type: 'list', ordered, items: [spans] }.
export const parseChatMarkdown = (source) => {
  const blocks = []
  let paragraph = []
  let list = null
  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: 'paragraph', spans: parseInline(paragraph.join('\n')) })
    paragraph = []
  }
  const flushList = () => {
    if (list) blocks.push(list)
    list = null
  }

  for (const line of String(source || '').replace(/\r\n?/g, '\n').split('\n')) {
    if (!line.trim()) {
      flushParagraph()
      flushList()
      continue
    }
    const heading = line.match(HASH_HEADING) || line.match(BOLD_HEADING)
    const bullet = line.match(BULLET)
    const numbered = line.match(NUMBERED)
    if (heading) {
      flushParagraph()
      flushList()
      blocks.push({ type: 'heading', spans: parseInline(heading[1]) })
    } else if (bullet || numbered) {
      flushParagraph()
      const ordered = Boolean(numbered)
      if (list && list.ordered !== ordered) flushList()
      if (!list) list = { type: 'list', ordered, start: ordered ? Number(numbered[1]) : 1, items: [] }
      list.items.push(parseInline(ordered ? numbered[2] : bullet[1]))
    } else if (list && /^\s{2,}\S/.test(line)) {
      // An indented line continues the previous list item.
      const item = list.items[list.items.length - 1]
      item.push({ text: ' ' }, ...parseInline(line.trim()))
    } else {
      flushList()
      paragraph.push(line)
    }
  }
  flushParagraph()
  flushList()
  return blocks
}

// "Indoor ride · 13 Oct: New 60 min best" → { meta: 'Indoor ride · 13 Oct', title: 'New 60 min best' }
export const splitConversationTitle = (title) => {
  const text = String(title || '')
  const match = text.match(/^([^:]{1,40}·[^:]{1,20}):\s+(.+)$/)
  return match ? { meta: match[1].trim(), title: match[2].trim() } : { meta: '', title: text }
}

const toDate = (value) => {
  if (!value) return null
  // SQLite CURRENT_TIMESTAMP is UTC without a zone marker.
  const text = String(value)
  const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(text) ? text : `${text.replace(' ', 'T')}Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

// Sidebar timestamp: "14:05" today, "Yesterday", "Mon" within a week, else "7 Oct".
export const conversationTime = (value, now = new Date()) => {
  const date = toDate(value)
  if (!date) return ''
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((startOfDay(now) - startOfDay(date)) / 86400000)
  if (days <= 0) return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  if (days === 1) return 'Yesterday'
  if (days < 7) return date.toLocaleDateString('en-GB', { weekday: 'short' })
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}
