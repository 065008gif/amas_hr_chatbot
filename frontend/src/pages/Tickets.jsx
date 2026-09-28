import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Inbox, Plus, Ticket as TicketIcon, X } from 'lucide-react'
import { api } from '../lib/api.js'
import { useSession } from '../lib/session.jsx'
import { fmtDate } from '../lib/format.js'
import { DemoTag, Empty, Portal, Skeleton, StatusBadge } from '../components/ui.jsx'

const FILTERS = ['All', 'Open', 'In Progress', 'Awaiting Employee', 'Resolved', 'Closed']

function NewTicket({ categories, onClose, onCreated }) {
  const [form, setForm] = useState({ category: categories[0] || 'Leave', summary: '', priority: 'Normal' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr(null)
    try { onCreated(await api('/ticket', { method: 'POST', body: form })) } catch (x) { setErr(x.message); setBusy(false) }
  }
  return (
    <Portal>
      <div className="drawer-backdrop" onClick={onClose} />
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="nt-title" onClick={onClose}>
        <form className="card" onSubmit={submit} onClick={(e) => e.stopPropagation()}>
          <div className="card-head"><h2 id="nt-title">Raise an HR ticket</h2><span className="spacer" /><button type="button" className="btn btn-ghost icon-btn" onClick={onClose} aria-label="Close"><X size={18} /></button></div>
          <div className="card-body stack">
            <div className="field"><label htmlFor="cat">Category</label>
              <select id="cat" className="select" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{categories.map((c) => <option key={c}>{c}</option>)}</select></div>
            <div className="field"><label htmlFor="sum">What do you need help with?</label>
              <textarea id="sum" className="textarea" maxLength={300} required minLength={3} value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} placeholder="Describe the request in a sentence or two. Avoid health or other sensitive details." />
              <span className="tiny muted">{form.summary.length}/300</span></div>
            <div className="field"><label htmlFor="pri">Priority</label>
              <select id="pri" className="select" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>{['Low', 'Normal', 'High', 'Urgent'].map((p) => <option key={p}>{p}</option>)}</select></div>
            {err && <div className="alert danger">{err}</div>}
          </div>
          <div className="card-body row" style={{ justifyContent: 'flex-end', borderTop: '1px solid var(--line)' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" disabled={busy || form.summary.trim().length < 3}>{busy ? 'Raising…' : 'Raise ticket'}</button>
          </div>
        </form>
      </div>
    </Portal>
  )
}

function Detail({ t, onClose }) {
  return (
    <Portal>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={`Ticket ${t.id}`}>
        <div className="panel-head"><span className="head-ic c-rose" aria-hidden="true"><TicketIcon size={16} /></span><div style={{ flex: 1 }}><div className="mono" style={{ fontWeight: 650, color: 'var(--ink)' }}>{t.id}</div><div className="tiny muted">{t.category} · {t.priority} priority</div></div>
          <button className="btn btn-ghost icon-btn" onClick={onClose} aria-label="Close"><X size={18} /></button></div>
        <div className="panel-body card-body stack">
          <div className="row"><StatusBadge status={t.status} /><span className="small muted">Raised {fmtDate(t.created_at)} via {t.source === 'chat' ? 'Ask Nia' : 'the portal'}</span></div>
          <div><div className="tiny muted" style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em' }}>Summary</div><p style={{ color: 'var(--ink)', marginTop: '.25rem' }}>{t.summary}</p></div>
          <div><div className="tiny muted" style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '.6rem' }}>History</div>
            <div className="timeline">{t.history.map((h, i) => (
              <div key={i} className="ev"><div className="row" style={{ gap: '.4rem' }}><StatusBadge status={h.status} /><span className="tiny muted">{fmtDate(h.at, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</span></div><div className="small" style={{ marginTop: '.2rem' }}>{h.note}</div></div>
            ))}</div></div>
          <div className="alert info small">Demo: tickets are stored for this demo only; no real HR team receives them.</div>
        </div>
      </aside>
    </Portal>
  )
}

export default function Tickets() {
  const { notify } = useSession()
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [filter, setFilter] = useState('All')
  const [params, setParams] = useSearchParams()
  const [showNew, setShowNew] = useState(params.get('new') === '1')
  const load = () => api('/tickets').then(setData).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])
  const selected = data?.tickets.find((t) => t.id === params.get('id'))
  const list = useMemo(() => (data?.tickets || []).filter((t) => filter === 'All' || t.status === filter), [data, filter])

  return (
    <div className="content fade-in">
      <div className="page-head">
        <div><h1>My Tickets</h1><p>Requests you raised with HR, from the portal or through Nia.</p></div>
        <span className="spacer" /><DemoTag />
        <button className="btn btn-primary" onClick={() => setShowNew(true)}><Plus size={16} />New ticket</button>
      </div>
      <div className="chips" style={{ marginTop: 0, marginBottom: '1rem' }} role="tablist" aria-label="Filter by status">
        {FILTERS.map((f) => <button key={f} role="tab" aria-selected={filter === f} className={`chip filter ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>{f}{data && f !== 'All' ? ` (${data.tickets.filter((t) => t.status === f).length})` : ''}</button>)}
      </div>
      <section className="card">
        {err && <div className="card-body"><div className="alert danger">{err}</div></div>}
        {!data && !err && <div className="card-body stack">{[0, 1, 2].map((i) => <Skeleton key={i} h={44} />)}</div>}
        {data && !list.length && <Empty icon={Inbox} title="No tickets here">{filter === 'All' ? 'Raise one with the New ticket button.' : 'Try another filter.'}</Empty>}
        {data && list.length > 0 && (
          <div className="table-wrap ticket-table">
            <table className="table">
              <thead><tr><th>Ticket</th><th>Summary</th><th>Status</th><th>Category</th><th>Raised</th></tr></thead>
              <tbody>{list.map((t) => (
                <tr key={t.id} className="clickable" tabIndex={0} onClick={() => setParams({ id: t.id })} onKeyDown={(e) => e.key === 'Enter' && setParams({ id: t.id })}>
                  <td className="mono" style={{ whiteSpace: 'nowrap', color: 'var(--ink)', fontWeight: 600 }}>{t.id}</td>
                  <td style={{ color: 'var(--ink)' }}>{t.summary}</td>
                  <td><StatusBadge status={t.status} /></td>
                  <td>{t.category}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>{fmtDate(t.created_at)}</td>
                </tr>))}</tbody>
            </table>
          </div>
        )}
        {data && list.length > 0 && (
          <div className="ticket-cards">
            {list.map((t) => (
              <button key={t.id} className="ticket-card" onClick={() => setParams({ id: t.id })}>
                <div className="row"><span className="mono tiny" style={{ color: 'var(--ink)', fontWeight: 650 }}>{t.id}</span><span className="spacer" /><StatusBadge status={t.status} /></div>
                <div className="t">{t.summary}</div>
                <div className="tiny muted">{t.category} · {fmtDate(t.created_at)}</div>
              </button>
            ))}
          </div>
        )}
      </section>
      {selected && <Detail t={selected} onClose={() => setParams({})} />}
      {showNew && data && <NewTicket categories={data.categories} onClose={() => { setShowNew(false); setParams({}) }}
        onCreated={(t) => { setShowNew(false); notify(`Ticket ${t.id} raised`); load(); setParams({ id: t.id }) }} />}
    </div>
  )
}
