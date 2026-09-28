import { createPortal } from 'react-dom'
import { AlertTriangle, BookOpen, CheckCircle2, CircleHelp, HelpCircle, LifeBuoy, ShieldAlert, SearchX, Wrench } from 'lucide-react'

// Route of a chat answer -> label, tone and icon. Colour is never the only signal: every badge has text.
export const ROUTES = {
  answer: { label: 'Answer', tone: 'ok', Icon: CheckCircle2 },
  not_found: { label: 'Not found', tone: 'info', Icon: SearchX },
  escalate: { label: 'Escalated to HR', tone: 'danger', Icon: LifeBuoy },
  tool: { label: 'Tool result', tone: 'tool', Icon: Wrench },
  refused: { label: 'Declined', tone: 'vio', Icon: ShieldAlert },
  clarify: { label: 'Needs detail', tone: 'warn', Icon: HelpCircle },
  error: { label: 'Service busy', tone: 'warn', Icon: AlertTriangle },
}

export function RouteBadge({ route, kind }) {
  const r = ROUTES[route] || { label: route, tone: '', Icon: CircleHelp }
  const label = route === 'answer' && ['greeting', 'thanks', 'bye', 'ai_disclosure'].includes(kind) ? 'Small talk' : r.label
  return <span className={`badge ${r.tone}`}><r.Icon aria-hidden="true" />{label}</span>
}

export const TICKET_STATUS = {
  Open: 'info', 'In Progress': 'tool', 'Awaiting Employee': 'warn', Resolved: 'ok', Closed: '',
}
export function StatusBadge({ status }) {
  return <span className={`badge ${TICKET_STATUS[status] ?? ''}`}><span className="status-dot" aria-hidden="true" />{status}</span>
}

export function Skeleton({ h = 16, w = '100%', style }) {
  return <div className="skeleton" style={{ height: h, width: w, ...style }} />
}

export function Empty({ icon: Icon = BookOpen, title, children }) {
  return (
    <div className="empty">
      <Icon size={32} aria-hidden="true" />
      <div style={{ fontWeight: 600, color: 'var(--ink)' }}>{title}</div>
      {children && <div className="small" style={{ marginTop: '.25rem' }}>{children}</div>}
    </div>
  )
}

export function DemoTag({ children = 'Demo data' }) {
  return <span className="badge outline">{children}</span>
}

// Drawers and modals render into <body>, outside any page stacking context.
export function Portal({ children }) {
  return createPortal(children, document.body)
}
