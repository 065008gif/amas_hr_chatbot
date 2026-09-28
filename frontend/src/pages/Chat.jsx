import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  AlertTriangle, ArrowUp, Bot, CalendarDays, CheckCircle2, FileText, GitCompareArrows, LifeBuoy, MapPin,
  Plane, RotateCcw, Scale, ShieldCheck, SquarePen, Ticket as TicketIcon, WifiOff, X,
} from 'lucide-react'
import { api } from '../lib/api.js'
import { load, save } from '../lib/storage.js'
import { useSession } from '../lib/session.jsx'
import { fmtDate } from '../lib/format.js'
import { leaveStyle } from '../lib/leave.js'
import PdfViewer from '../components/PdfViewer.jsx'
import { DemoTag, RouteBadge, StatusBadge } from '../components/ui.jsx'

const GRADES = ['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7', 'L8']
const LOCATIONS = ['Bengaluru', 'Pune', 'Hyderabad', 'Chennai', 'Noida']
const STARTERS = [
  { Icon: CalendarDays, c: 'c-indigo', q: 'How many days of paternity leave do I get?' },
  { Icon: Plane, c: 'c-sky', q: 'Can I claim a cab from the airport at L4?' },
  { Icon: Scale, c: 'c-amber', q: 'What is the notice period if I resign at L5?' },
  { Icon: FileText, c: 'c-emerald', q: 'What is my leave balance?' },
]
const WELCOME = "Hi, I'm Nia, Nexora's AI HR assistant. I'm an AI, not a person. I answer only from Nexora's HR policy documents and show the exact page for every answer. If the documents don't cover something, I'll say so and can raise a ticket for a person in HR."
const uid = () => Math.random().toString(36).slice(2, 10)

// Colour of a Nia bubble's left border: green answered, amber conflict, rose escalated, sky not found.
function routeClass(r) {
  if (!r) return 'r-intro'
  if (r.route === 'answer' && r.conflicts?.length) return 'r-conflict'
  return `r-${r.route}`
}

// "[S1][S2]" -> clickable reference chips; blank lines -> paragraphs.
function AnswerText({ text, citations, onCite }) {
  const byId = Object.fromEntries((citations || []).map((c) => [c.id, c]))
  const paras = String(text || '').split(/\n{2,}/)
  return (
    <div className="answer">
      {paras.map((p, i) => (
        <p key={i}>
          {p.split(/((?:\[S\d+\])+[.,;:!?)]?)/g).map((part, j) => {
            if (!/^\[S\d+\]/.test(part)) return <Fragment key={j}>{part.split('\n').map((l, k) => <Fragment key={k}>{k > 0 && <br />}{l}</Fragment>)}</Fragment>
            const punct = part.replace(/(\[S\d+\])+/, '')
            const refs = (part.match(/S\d+/g) || []).map((id) => byId[id]).filter(Boolean)
            return (
              <span key={j} className="cite-group">
                {refs.map((c) => <button key={c.id} className="cite-ref" onClick={() => onCite(c)} title={c.label} aria-label={`Source: ${c.label}`}>{c.id.slice(1)}</button>)}
                {punct}
              </span>
            )
          })}
        </p>
      ))}
    </div>
  )
}

function LeaveCard({ data }) {
  return (
    <div className="inline-card">
      <div className="row" style={{ marginBottom: '.6rem' }}><b style={{ color: 'var(--ink)' }}>Leave balance</b><span className="small muted">as of {fmtDate(data.as_of)}</span><div className="spacer" /><DemoTag /></div>
      <div className="grid grid-4" style={{ gap: '.6rem' }}>
        {data.balances.map((b, i) => (
          <div key={b.code} className={`card stat ${leaveStyle(b.code, i).c}`} style={{ padding: '.6rem .7rem' }} title={b.detail}>
            <div className="tiny" style={{ fontWeight: 650, color: 'var(--text)' }}>{b.type}</div>
            <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--ink)' }}>{b.balance}<span className="tiny muted"> days</span></div>
          </div>
        ))}
      </div>
    </div>
  )
}

function TicketCard({ t }) {
  if (!t) return null
  return (
    <div className="inline-card row wrap" style={{ gap: '.7rem' }}>
      <TicketIcon size={18} style={{ color: 'var(--danger-text)', flex: 'none' }} />
      <div style={{ flex: 1, minWidth: 180 }}>
        <div className="mono" style={{ fontWeight: 600, color: 'var(--ink)' }}>{t.id}</div>
        <div className="small muted">{t.category} · {t.summary}</div>
      </div>
      <StatusBadge status={t.status} />
    </div>
  )
}

function BotMessage({ m, onCite, onFollow, onTicket, activeCite, onRetry, busy }) {
  const r = m.response
  if (m.error) {
    const Icon = m.error.kind === 'offline' ? WifiOff : AlertTriangle
    return (
      <div className="alert warn" role="alert">
        <Icon size={16} />
        <div style={{ flex: 1 }}>
          <b>{m.error.kind === 'offline' ? "You're offline" : m.error.kind === 'rate_limit' ? 'Please slow down a little' : m.error.kind === 'warming' ? 'Nia is waking up' : "That didn't go through"}</b>
          <div>{m.error.message}</div>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={onRetry} disabled={busy}><RotateCcw size={14} />Retry</button>
      </div>
    )
  }
  const tool = r.tool_result
  return (
    <>
      <div className="msg-meta">
        <span className="name">Nia</span><span className="badge outline">AI assistant</span><RouteBadge route={r.route} kind={r.kind} />
        {r.cache_hit && <span className="badge outline" title="Same question answered before: served from cache">Cached</span>}
      </div>
      <AnswerText text={r.answer} citations={r.citations} onCite={onCite} />
      {r.conflicts?.map((c, i) => (
        <div key={i} className="conflict">
          <div className="row" style={{ gap: '.4rem', marginBottom: '.2rem' }}><GitCompareArrows size={15} /><b>Sources disagree{c.topic ? `: ${c.topic}` : ''}</b></div>
          <div><b>{c.prevailing}</b> prevails over <b>{c.other}</b>.</div>
          {c.reason && <div className="small" style={{ marginTop: '.2rem' }}>{c.reason}</div>}
        </div>
      ))}
      {tool?.type === 'leave_balance' && <LeaveCard data={tool.data} />}
      {tool?.type === 'ticket' && <TicketCard t={tool.data} />}
      {tool?.type === 'ticket_list' && tool.data.map((t) => <TicketCard key={t.id} t={t} />)}
      {r.escalation && (
        <div className="inline-card escalation row" style={{ gap: '.6rem' }}>
          <LifeBuoy size={18} style={{ flex: 'none' }} />
          <div className="small">This topic is handled by people, not by Nia. Your conversation is not shared with HR unless you choose to raise a ticket.</div>
        </div>
      )}
      {r.citations?.length > 0 && (
        <div className="chips" aria-label="Sources">
          {r.citations.map((c) => (
            <button key={c.id} className={`chip cite ${activeCite?.chunk_id === c.chunk_id && activeCite?.page === c.page ? 'active' : ''}`} onClick={() => onCite(c)}>
              <FileText aria-hidden="true" />{c.label}{c.verified && <CheckCircle2 aria-label="page verified" style={{ color: 'inherit', opacity: .8 }} />}
            </button>
          ))}
        </div>
      )}
      {r.ticket_offer && !m.ticket && (
        <div className="inline-card row wrap" style={{ gap: '.6rem' }}>
          <TicketIcon size={18} style={{ color: 'var(--danger-text)', flex: 'none' }} />
          <div className="small" style={{ flex: 1, minWidth: 200 }}>Want a person in HR to follow up? I'll raise a <b>{r.ticket_offer.category}</b> ticket{r.ticket_offer.priority === 'High' ? ' marked high priority' : ''}.</div>
          <button className="btn btn-primary btn-sm" onClick={() => onTicket(m)} disabled={m.ticketBusy}>{m.ticketBusy ? 'Raising…' : 'Raise HR ticket'}</button>
        </div>
      )}
      {m.ticket && <TicketCard t={m.ticket} />}
      {r.follow_ups?.length > 0 && (
        <>
          <div className="follow-label">You could also ask</div>
          <div className="chips">{r.follow_ups.map((f) => <button key={f} className="chip" onClick={() => onFollow(f)} disabled={busy}>{f}</button>)}</div>
        </>
      )}
    </>
  )
}

export default function Chat() {
  const { employee, notify } = useSession()
  const key = `nxr.chat.${employee.employee_id}`
  const [messages, setMessages] = useState(() => load(key, []))
  const [profile, setProfile] = useState(() => load(`nxr.profile.${employee.employee_id}`, { grade: '', location: '' }))
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [panel, setPanel] = useState(null)
  const [params, setParams] = useSearchParams()
  const endRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { save(key, messages.slice(-60)) }, [key, messages])
  useEffect(() => { save(`nxr.profile.${employee.employee_id}`, profile) }, [employee.employee_id, profile])
  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }) }, [messages, busy])
  useEffect(() => {
    const q = params.get('q')
    if (q && !busy) { setParams({}, { replace: true }); send(q) }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const history = useMemo(() => messages.filter((m) => !m.error).slice(-8).map((m) => (
    m.role === 'user' ? { role: 'user', content: m.content.slice(0, 1000), query: m.query }
      : { role: 'assistant', content: (m.response?.answer || '').slice(0, 1000), route: m.response?.route }
  )), [messages])

  async function send(raw) {
    const msg = String(raw ?? text).trim()
    if (!msg || busy) return
    const userTurns = messages.filter((m) => m.role === 'user').length
    if (userTurns >= 20) { notify('This chat reached 20 questions. Start a new chat to continue.'); return }
    const user = { id: uid(), role: 'user', content: msg }
    setMessages((ms) => [...ms.filter((m) => !m.error), user])
    setText('')
    setBusy(true)
    try {
      const r = await api('/chat', { method: 'POST', body: { message: msg, profile, history } })
      setMessages((ms) => ms.map((m) => (m.id === user.id ? { ...m, query: r.standalone_query } : m)).concat({ id: uid(), role: 'assistant', response: r }))
      if (r.profile && (r.profile.grade !== profile.grade || r.profile.location !== profile.location)) {
        setProfile({ grade: r.profile.grade || '', location: r.profile.location || '' })
      }
    } catch (e) {
      setMessages((ms) => [...ms, { id: uid(), role: 'assistant', error: { kind: e.kind, message: e.message }, retry: msg }])
    } finally {
      setBusy(false)
      inputRef.current?.focus()
    }
  }

  function retry(m) {
    setMessages((ms) => {
      const idx = ms.findIndex((x) => x.id === m.id)
      return ms.slice(0, Math.max(0, idx - 1))
    })
    setTimeout(() => send(m.retry), 0)
  }

  async function raiseTicket(m) {
    setMessages((ms) => ms.map((x) => (x.id === m.id ? { ...x, ticketBusy: true } : x)))
    try {
      const o = m.response.ticket_offer
      const t = await api('/ticket', { method: 'POST', body: { category: o.category, summary: o.summary, priority: o.priority || 'Normal' } })
      setMessages((ms) => ms.map((x) => (x.id === m.id ? { ...x, ticket: t, ticketBusy: false } : x)))
      notify(`Ticket ${t.id} raised`)
    } catch (e) {
      setMessages((ms) => ms.map((x) => (x.id === m.id ? { ...x, ticketBusy: false } : x)))
      notify(e.message)
    }
  }

  const newChat = () => { setMessages([]); setPanel(null); inputRef.current?.focus() }
  const onKey = (e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send() } }

  return (
    <div className={`chat-layout ${panel ? 'with-panel' : ''}`}>
      <section className="chat-col" aria-label="Chat with Nia">
        <div className="profile-bar">
          <span className="muted row" style={{ gap: '.3rem' }}><MapPin size={14} />Answer for</span>
          <label className="sr-only" htmlFor="grade">Grade</label>
          <select id="grade" className="select" value={profile.grade} onChange={(e) => setProfile((p) => ({ ...p, grade: e.target.value }))}>
            <option value="">Any grade</option>{GRADES.map((g) => <option key={g}>{g}</option>)}
          </select>
          <label className="sr-only" htmlFor="loc">Location</label>
          <select id="loc" className="select" value={profile.location} onChange={(e) => setProfile((p) => ({ ...p, location: e.target.value }))}>
            <option value="">Any location</option>{LOCATIONS.map((l) => <option key={l}>{l}</option>)}
          </select>
          {(profile.grade !== employee.grade || profile.location !== employee.location) && (
            <button className="btn btn-ghost btn-sm" onClick={() => setProfile({ grade: employee.grade, location: employee.location })}>Use mine ({employee.grade}, {employee.location})</button>
          )}
          <div className="spacer" />
          <button className="btn btn-secondary btn-sm" onClick={newChat} disabled={busy || !messages.length}><SquarePen size={14} />New chat</button>
        </div>

        <div className="messages" aria-live="polite">
          <div className="messages-inner">
            {!messages.length ? (
              <div className="welcome fade-in">
                <div className="bot-avatar"><Bot size={24} /></div>
                <h2 style={{ fontSize: '1.35rem' }}>Ask Nia about Nexora's HR policies</h2>
                <p className="muted" style={{ maxWidth: 560, margin: '.5rem auto 0' }}>{WELCOME}</p>
                <div className="starters">
                  {STARTERS.map(({ Icon, c, q }) => <button key={q} className={`starter ${c}`} onClick={() => send(q)}><span className="s-ic" aria-hidden="true"><Icon size={17} /></span>{q}</button>)}
                </div>
              </div>
            ) : (
              <div className="msg bot fade-in">
                <div className="bot-avatar" aria-hidden="true">N</div>
                <div className="bubble r-intro"><div className="msg-meta"><span className="name">Nia</span><span className="badge outline">AI assistant</span></div><p>{WELCOME}</p></div>
              </div>
            )}
            {messages.map((m) => (m.role === 'user' ? (
              <div key={m.id} className="msg user fade-in"><div className="bubble">{m.content}</div></div>
            ) : (
              <div key={m.id} className="msg bot fade-in">
                <div className="bot-avatar" aria-hidden="true">N</div>
                <div className={`bubble ${routeClass(m.response)}`} style={m.error ? { padding: 0, border: 0, background: 'none', boxShadow: 'none', width: '100%' } : undefined}>
                  <BotMessage m={m} busy={busy} activeCite={panel} onCite={setPanel} onFollow={send} onTicket={raiseTicket} onRetry={() => retry(m)} />
                </div>
              </div>
            )))}
            {busy && (
              <div className="msg bot fade-in" aria-label="Nia is typing">
                <div className="bot-avatar" aria-hidden="true">N</div>
                <div className="bubble r-intro"><div className="msg-meta"><span className="name">Nia</span><span className="small muted">is checking the policies…</span></div><div className="typing"><span /><span /><span /></div></div>
              </div>
            )}
            <div ref={endRef} />
          </div>
        </div>

        <div className="composer-wrap">
          <form className="composer" onSubmit={(e) => { e.preventDefault(); send() }}>
            <label htmlFor="msg" className="sr-only">Your question</label>
            <textarea id="msg" ref={inputRef} rows={1} value={text} maxLength={800} autoFocus placeholder={window.innerWidth < 560 ? 'Ask an HR question…' : 'Ask about leave, pay, travel, exits, IT policy…'}
              onChange={(e) => { setText(e.target.value); e.target.style.height = 'auto'; e.target.style.height = `${Math.min(160, e.target.scrollHeight)}px` }}
              onKeyDown={onKey} />
            <button className="btn btn-primary icon-btn" type="submit" disabled={busy || !text.trim()} aria-label="Send"><ArrowUp size={18} /></button>
          </form>
          <div className="composer-foot">
            <span className="ai-banner"><ShieldCheck size={13} />AI assistant, not HR advice. Answers come from Nexora's policy documents (fictional, college project).</span>
            <span className="spacer" />
            <span className="hint">Enter to send · Shift+Enter for a new line · {text.length}/800</span>
          </div>
        </div>
      </section>

      {panel && (
        <aside className="panel" aria-label="Cited source">
          <div className="panel-head">
            <span className="head-ic c-sky" aria-hidden="true"><FileText size={16} /></span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 650, color: 'var(--ink)', fontSize: '.92rem' }}>{panel.document}</div>
              <div className="tiny muted">{panel.number} · v{panel.version}</div>
            </div>
            <button className="btn btn-ghost icon-btn" onClick={() => setPanel(null)} aria-label="Close source panel"><X size={18} /></button>
          </div>
          <PdfViewer docId={panel.doc_id} page={panel.page} highlight={(
            <div className="quote">
              “{panel.snippet}”
              <div className="src">
                <span>{panel.label}</span>
                {panel.verified ? <span className="badge ok"><CheckCircle2 />Text found on this page</span> : <span className="badge warn">Page not verified</span>}
              </div>
            </div>
          )} />
        </aside>
      )}
    </div>
  )
}
