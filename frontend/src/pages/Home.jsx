import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, BookOpenText, CalendarCheck, FileClock, MessageSquareText, Plus, Ticket as TicketIcon } from 'lucide-react'
import { api } from '../lib/api.js'
import { useSession } from '../lib/session.jsx'
import { fmtDate, greeting, shortDoc } from '../lib/format.js'
import { DemoTag, Empty, Skeleton, StatusBadge } from '../components/ui.jsx'

export default function Home() {
  const { employee } = useSession()
  const nav = useNavigate()
  const [lb, setLb] = useState(null)
  const [tickets, setTickets] = useState(null)
  const [circs, setCircs] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api('/leave-balance').then(setLb).catch((e) => setErr(e.message))
    api('/tickets').then((d) => setTickets(d.tickets)).catch(() => setTickets([]))
    api('/circulars?limit=5').then((d) => setCircs(d.circulars)).catch(() => setCircs([]))
  }, [])

  const first = employee.name.split(' ')[0]
  const open = tickets?.filter((t) => !['Resolved', 'Closed'].includes(t.status)).length ?? 0

  return (
    <div className="content fade-in">
      <section className="hero">
        <div className="small" style={{ color: '#b9cce8' }}>{new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</div>
        <h1 style={{ marginTop: '.25rem' }}>{greeting()}, {first}</h1>
        <p>{employee.designation} · Grade {employee.grade} · {employee.location}{open ? ` · ${open} open ticket${open > 1 ? 's' : ''}` : ''}</p>
        <div className="quick">
          <button className="btn primary" onClick={() => nav('/chat')}><MessageSquareText size={16} />Ask Nia</button>
          <button className="btn" onClick={() => nav('/chat?q=' + encodeURIComponent('What is my leave balance?'))}><CalendarCheck size={16} />Check leave</button>
          <button className="btn" onClick={() => nav('/tickets?new=1')}><Plus size={16} />Raise ticket</button>
          <button className="btn" onClick={() => nav('/library')}><BookOpenText size={16} />Browse policies</button>
        </div>
      </section>

      <div className="row" style={{ margin: '1.75rem 0 .9rem' }}>
        <h2>Leave balance</h2><DemoTag />
        <span className="spacer" />
        {lb && <span className="small muted">as of {fmtDate(lb.as_of)}</span>}
      </div>
      {err && <div className="alert danger">{err}</div>}
      <div className="grid grid-4">
        {!lb && !err && [0, 1, 2, 3].map((i) => <div key={i} className="card stat"><Skeleton h={12} w="50%" /><Skeleton h={30} w="40%" style={{ marginTop: 10 }} /><Skeleton h={6} style={{ marginTop: 14 }} /></div>)}
        {lb?.balances.map((b) => (
          <div key={b.code} className="card stat" title={b.detail}>
            <div className="k">{b.type}</div>
            <div className="v">{b.balance}<small>of {b.total} days left</small></div>
            <div className="meter" role="img" aria-label={`${b.balance} of ${b.total} days left`}><span style={{ width: `${b.total ? Math.min(100, (b.balance / b.total) * 100) : 0}%` }} /></div>
            <div className="d">{b.taken} taken this Leave Year</div>
          </div>
        ))}
      </div>

      <div className="grid grid-main" style={{ marginTop: '1.75rem' }}>
        <section className="card">
          <div className="card-head"><TicketIcon size={17} className="muted" /><h2>Recent tickets</h2><span className="spacer" /><Link to="/tickets" className="small row" style={{ gap: '.2rem' }}>View all<ArrowRight size={14} /></Link></div>
          {!tickets && <div className="card-body stack"><Skeleton h={40} /><Skeleton h={40} /></div>}
          {tickets?.length === 0 && <Empty icon={TicketIcon} title="No tickets yet">Raise one from Ask Nia or My Tickets.</Empty>}
          {tickets?.slice(0, 4).map((t) => (
            <button key={t.id} className="list-item" onClick={() => nav(`/tickets?id=${t.id}`)}>
              <div className="ic"><TicketIcon size={16} /></div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="t" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.summary}</div>
                <div className="tiny muted"><span className="mono">{t.id}</span> · {t.category} · {fmtDate(t.created_at)}</div>
              </div>
              <StatusBadge status={t.status} />
            </button>
          ))}
        </section>

        <section className="card">
          <div className="card-head"><FileClock size={17} className="muted" /><h2>Recent policy circulars</h2></div>
          {!circs && <div className="card-body stack"><Skeleton h={40} /><Skeleton h={40} /><Skeleton h={40} /></div>}
          {circs?.map((c) => (
            <button key={c.no} className="list-item" onClick={() => nav(`/library/${c.doc_id}?page=${c.page}`)}>
              <div className="ic" style={{ background: 'var(--accent-50)', color: 'var(--accent)' }}><FileClock size={16} /></div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="t">{c.subject}</div>
                <div className="tiny muted"><span className="mono">{c.no}</span> · {shortDoc(c.document)} · effective {fmtDate(c.effective)}</div>
              </div>
            </button>
          ))}
        </section>
      </div>
    </div>
  )
}
