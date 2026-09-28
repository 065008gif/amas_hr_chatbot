import { useEffect, useState } from 'react'
import { ArrowRight, Info } from 'lucide-react'
import { api } from '../lib/api.js'
import { initials } from '../lib/format.js'
import { useSession } from '../lib/session.jsx'
import { Skeleton } from '../components/ui.jsx'

export default function SignIn() {
  const { signIn } = useSession()
  const [list, setList] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { api('/demo-employees').then((d) => setList(d.employees)).catch((e) => setErr(e.message)) }, [])
  return (
    <div className="center-screen">
      <div className="signin fade-in">
        <div className="row" style={{ gap: '.8rem' }}>
          <div className="brand-mark" aria-hidden="true">N</div>
          <div><div className="brand-name" style={{ fontSize: '1.1rem' }}>Nexora People Portal</div><div className="brand-sub">with Nia, the AI HR assistant</div></div>
        </div>
        <h1 style={{ marginTop: '1.5rem' }}>Choose a demo employee</h1>
        <p className="muted" style={{ marginTop: '.35rem' }}>
          There is no password: this is a demo. Each account is a fictional employee with a different grade and location,
          so you can see how answers change.
        </p>
        {err && <div className="alert danger" style={{ marginTop: '1rem' }}>{err}</div>}
        <div className="accounts">
          {!list && !err && [1, 2, 3, 4, 5].map((i) => <div key={i} className="card account"><Skeleton h={44} w={44} style={{ borderRadius: '50%' }} /><div style={{ flex: 1 }}><Skeleton h={14} /><Skeleton h={12} w="60%" style={{ marginTop: 6 }} /></div></div>)}
          {list?.map((e) => (
            <button key={e.employee_id} className="card account" onClick={() => signIn(e)}>
              <div className="avatar lg" aria-hidden="true">{initials(e.name)}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 650, color: 'var(--ink)' }}>{e.name}</div>
                <div className="small muted">{e.designation}</div>
                <div className="row" style={{ marginTop: '.3rem', gap: '.3rem' }}>
                  <span className="badge brand">{e.grade}</span><span className="badge">{e.location}</span>
                </div>
              </div>
              <ArrowRight size={16} className="muted" />
            </button>
          ))}
        </div>
        <div className="alert info" style={{ marginTop: '1.25rem' }}>
          <Info size={16} />
          <div>All people, policies and numbers here are invented for a college project. Nia is an AI assistant and does not give HR or legal advice.</div>
        </div>
      </div>
    </div>
  )
}
