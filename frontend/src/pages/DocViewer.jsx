import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { getDocs } from '../lib/docs.js'
import { fmtDate } from '../lib/format.js'
import PdfViewer from '../components/PdfViewer.jsx'

export default function DocViewer() {
  const { docId } = useParams()
  const [params, setParams] = useSearchParams()
  const [doc, setDoc] = useState(null)
  const page = parseInt(params.get('page') || '1', 10) || 1
  useEffect(() => { getDocs().then((ds) => setDoc(ds.find((d) => d.doc_id === docId) || null)) }, [docId])
  const jump = (p) => setParams({ page: String(p) }, { replace: true })

  return (
    <div className="viewer-layout fade-in">
      <nav className="toc" aria-label="Sections">
        <div style={{ padding: '1rem' }}>
          <Link to="/library" className="small row" style={{ gap: '.3rem' }}><ArrowLeft size={14} />All policies</Link>
          <div style={{ fontWeight: 650, color: 'var(--ink)', marginTop: '.8rem', lineHeight: 1.3 }}>{doc?.title}</div>
          {doc && <div className="tiny muted" style={{ marginTop: '.25rem' }}>{doc.number} · v{doc.version} · effective {fmtDate(doc.effective_date)} · {doc.pages} pages</div>}
        </div>
        {doc?.sections.map((s) => (
          <button key={s.no} onClick={() => jump(s.page)}><span className="muted" style={{ minWidth: 22 }}>{/^\d/.test(s.no) ? s.no : s.no.replace('Annexure ', '')}</span><span>{s.title}</span><span className="pg">{s.page}</span></button>
        ))}
        {doc?.circulars.length > 0 && <div className="nav-label">Amendment circulars</div>}
        {doc?.circulars.map((c) => (
          <button key={c.no} onClick={() => jump(c.page)}><span>{c.subject}<br /><span className="tiny muted mono">{c.no}</span></span><span className="pg">{c.page}</span></button>
        ))}
      </nav>
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, minWidth: 0 }}>
        <div className="profile-bar" style={{ display: 'flex' }}>
          <Link to="/library" className="btn btn-ghost btn-sm"><ArrowLeft size={14} />Library</Link>
          <b style={{ color: 'var(--ink)' }}>{doc?.title}</b>
        </div>
        <PdfViewer docId={docId} page={page} onPageChange={jump} />
      </div>
    </div>
  )
}
