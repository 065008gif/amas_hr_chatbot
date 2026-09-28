import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight, BookOpenText, CalendarCheck, FileClock, MessageSquareText, Plus, Sparkles, Ticket as TicketIcon,
} from 'lucide-react'
import { api } from '../lib/api.js'
import { leaveStyle } from '../lib/leave.js'
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
        <div className="nia-orb" aria-hidden="true"><Sparkles size={32} /></div>
        <div className="hero-text">
          <div className="date">{new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</div>
          <h1>{greeting()}, {first}</h1>
          <p>Nia can answer HR policy questions with the exact page as proof, check your leave, or raise a ticket.</p>
          <span className="pill">{employee.designation}</span><span className="pill">Grade {employee.grade}</span><span className="pill">{employee.location}</span>
          {open > 0 && <span className="pill"><TicketIcon size={13} />{open} open ticket{open > 1 ? 's' : ''}</span>}
        </div>
        <button className="btn hero-cta" onClick={() => nav('/chat')}><MessageSquareText size={17} />Ask Nia</button>
      </section>

      <nav className="tiles" aria-label="Quick actions">
        {[
          { c: 'c-violet', Icon: MessageSquareText, t: 'Ask Nia', s: 'Policy answers with page citations', go: '/chat' },
          { c: 'c-emerald', Icon: CalendarCheck, t: 'Check leave', s: 'Your balance, straight from Nia', go: '/chat?q=' + encodeURIComponent('What is my leave balance?') },
          { c: 'c-rose', Icon: Plus, t: 'Raise ticket', s: 'Hand a request to a person in HR', go: '/tickets?new=1' },
          { c: 'c-sky', Icon: BookOpenText, t: 'Browse policies', s: '9 documents, searchable', go: '/library' },
        ].map(({ c, Icon, t, s: sub, go }) => (
          <button key={t} className={`tile ${c}`} onClick={() => nav(go)}>
            <span className="tile-ic" aria-hidden="true"><Icon size={21} /></span>
            <span className="tile-text"><b>{t}</b><span className="tile-sub">{sub}</span></span>
            <ArrowRight size={16} className="arrow" aria-hidden="true" />
          </button>
        ))}
      </nav>

      <div className="row" style={{ margin: '1.75rem 0 .9rem' }}>
        <h2 style={{ whiteSpace: 'nowrap' }}>Leave balance</h2><DemoTag />
        <span className="spacer" />
        {lb && <span className="small muted as-of">as of {fmtDate(lb.as_of)}</span>}
      </div>
      {err && <div className="alert danger">{err}</div>}
      <div className="grid grid-4">
        {!lb && !err && [0, 1, 2, 3].map((i) => <div key={i} className="card stat"><Skeleton h={12} w="50%" /><Skeleton h={30} w="40%" style={{ marginTop: 10 }} /><Skeleton h={6} style={{ marginTop: 14 }} /></div>)}
        {lb?.balances.map((b, i) => {
          const st = leaveStyle(b.code, i)
          return (
          <div key={b.code} className={`card stat ${st.c}`} title={b.detail}>
            <div className="k"><span className="stat-ic" aria-hidden="true"><st.Icon size={17} /></span>{b.type}</div>
            <div className="v">{b.balance}<small>of {b.total} days left</small></div>
            <div className="meter" role="img" aria-label={`${b.balance} of ${b.total} days left`}><span style={{ width: `${b.total ? Math.min(100, (b.balance / b.total) * 100) : 0}%` }} /></div>
            <div className="d">{b.taken} taken this Leave Year</div>
          </div>
          )
        })}
      </div>

      <div className="grid grid-main" style={{ marginTop: '1.75rem' }}>
        <section className="card">
          <div className="card-head"><span className="head-ic c-rose" aria-hidden="true"><TicketIcon size={16} /></span><h2>Recent tickets</h2><span className="spacer" /><Link to="/tickets" className="small row" style={{ gap: '.2rem' }}>View all<ArrowRight size={14} /></Link></div>
          {!tickets && <div className="card-body stack"><Skeleton h={40} /><Skeleton h={40} /></div>}
          {tickets?.length === 0 && <Empty icon={TicketIcon} title="No tickets yet">Raise one from Ask Nia or My Tickets.</Empty>}
          {tickets?.slice(0, 4).map((t) => (
            <button key={t.id} className="list-item" onClick={() => nav(`/tickets?id=${t.id}`)}>
              <div className="ic c-rose"><TicketIcon size={16} /></div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="t" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.summary}</div>
                <div className="tiny muted"><span className="mono">{t.id}</span> · {t.category} · {fmtDate(t.created_at)}</div>
              </div>
              <StatusBadge status={t.status} />
            </button>
          ))}
        </section>

        <section className="card">
          <div className="card-head"><span className="head-ic c-amber" aria-hidden="true"><FileClock size={16} /></span><h2>Recent policy circulars</h2></div>
          {!circs && <div className="card-body stack"><Skeleton h={40} /><Skeleton h={40} /><Skeleton h={40} /></div>}
          {circs?.map((c) => (
            <button key={c.no} className="list-item" onClick={() => nav(`/library/${c.doc_id}?page=${c.page}`)}>
              <div className="ic c-amber"><FileClock size={16} /></div>
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
