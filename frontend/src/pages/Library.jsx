import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileClock, FileText, Hash, Search } from 'lucide-react'
import { getDocs } from '../lib/docs.js'
import { fmtDate } from '../lib/format.js'
import { Empty, Skeleton } from '../components/ui.jsx'

// One accent per document, so a policy is recognisable at a glance (the title is always shown too).
const DOC_COLOURS = ['c-indigo', 'c-violet', 'c-rose', 'c-amber', 'c-emerald', 'c-sky']
const docColour = (docId) => DOC_COLOURS[(parseInt(docId, 10) - 1) % DOC_COLOURS.length] || 'c-indigo'

export default function Library() {
  const nav = useNavigate()
  const [docs, setDocs] = useState(null)
  const [err, setErr] = useState(null)
  const [q, setQ] = useState('')
  useEffect(() => { getDocs().then(setDocs).catch((e) => setErr(e.message)) }, [])

  const results = useMemo(() => {
    const term = q.trim().toLowerCase()
    return (docs || []).map((d) => {
      if (!term) return { d, matches: [] }
      const inTitle = `${d.title} ${d.number}`.toLowerCase().includes(term)
      const matches = [
        ...d.sections.filter((s) => s.title.toLowerCase().includes(term)).map((s) => ({ kind: 'section', label: `${/^\d/.test(s.no) ? `Section ${s.no}` : s.no}: ${s.title}`, page: s.page })),
        ...d.circulars.filter((c) => `${c.no} ${c.subject}`.toLowerCase().includes(term)).map((c) => ({ kind: 'circular', label: `${c.no}: ${c.subject}`, page: c.page })),
      ]
      return inTitle || matches.length ? { d, matches } : null
    }).filter(Boolean)
  }, [docs, q])

  return (
    <div className="content fade-in">
      <div className="page-head">
        <div><h1>Policy Library</h1><p>Nexora's 9 HR policy documents (fictional). Search titles, sections and amendment circulars.</p></div>
      </div>
      <div className="search-box">
        <Search size={18} aria-hidden="true" />
        <label htmlFor="lib-q" className="sr-only">Search policies</label>
        <input id="lib-q" className="input" style={{ border: 0, boxShadow: 'none', padding: '.35rem .2rem' }} placeholder="Try “gratuity”, “hotel”, “HR/CIR/2025”, “probation”…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {err && <div className="alert danger">{err}</div>}
      <div className="grid grid-3">
        {!docs && !err && Array.from({ length: 6 }).map((_, i) => <div key={i} className="card card-pad"><Skeleton h={48} w={40} /><Skeleton h={16} style={{ marginTop: 12 }} /><Skeleton h={12} w="60%" style={{ marginTop: 8 }} /></div>)}
        {results.map(({ d, matches }) => (
          <button key={d.doc_id} className={`card doc-card ${docColour(d.doc_id)}`} onClick={() => nav(`/library/${d.doc_id}`)}>
            <div className="row" style={{ gap: '.8rem', alignItems: 'flex-start' }}>
              <div className="doc-icon"><FileText size={20} /></div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 650, color: 'var(--ink)', lineHeight: 1.3 }}>{d.title}</div>
                <div className="tiny muted mono" style={{ marginTop: '.2rem' }}>{d.number}</div>
              </div>
            </div>
            <div className="doc-meta">
              <span className="badge tool">v{d.version}</span>
              <span className="badge">Effective {fmtDate(d.effective_date)}</span>
              <span className="badge">{d.pages} pages</span>
              {d.circulars.length > 0 && <span className="badge outline">{d.circulars.length} circulars</span>}
            </div>
            {matches.slice(0, 3).map((m) => (
              <span key={m.label} className="match" role="link" tabIndex={0}
                onClick={(e) => { e.stopPropagation(); nav(`/library/${d.doc_id}?page=${m.page}`) }}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); nav(`/library/${d.doc_id}?page=${m.page}`) } }}>
                {m.kind === 'circular' ? <FileClock size={14} /> : <Hash size={14} />}<span style={{ flex: 1 }}>{m.label}</span><span className="muted">p. {m.page}</span>
              </span>
            ))}
            {matches.length > 3 && <span className="tiny muted">+{matches.length - 3} more matches</span>}
          </button>
        ))}
      </div>
      {docs && !results.length && <Empty icon={Search} title={`No policy matches “${q}”`}>Try a broader word, or ask Nia in plain language.</Empty>}
      <p className="tiny muted" style={{ marginTop: '1.5rem' }}>All documents are fictional and were generated for a college project. They are not real HR policy or legal advice.</p>
    </div>
  )
}
