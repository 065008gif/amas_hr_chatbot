import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'
import Layout from './components/Layout.jsx'
import WarmUp from './components/WarmUp.jsx'
import { API_URL } from './lib/api.js'
import { SessionProvider, useSession } from './lib/session.jsx'
import SignIn from './pages/SignIn.jsx'
import Home from './pages/Home.jsx'
import Chat from './pages/Chat.jsx'
import Tickets from './pages/Tickets.jsx'
import Library from './pages/Library.jsx'
import DocViewer from './pages/DocViewer.jsx'
import Insights from './pages/Insights.jsx'
import About from './pages/About.jsx'

// The free backend sleeps when idle; poll /health until it reports ready (up to ~4 minutes).
function useBackendReady() {
  const [state, setState] = useState({ ready: false, attempts: 0, status: 'connecting', error: null })
  const stopped = useRef(false)
  const check = useCallback(async (attempt = 0) => {
    if (stopped.current) return
    try {
      const r = await fetch(`${API_URL}/health`, { cache: 'no-store' })
      const h = await r.json()
      if (h.ready) { setState({ ready: true, attempts: attempt, status: 'ok', error: null }); return }
      setState({ ready: false, attempts: attempt, status: h.status || 'warming_up', error: h.warm_error })
    } catch {
      setState((s) => ({ ...s, attempts: attempt, status: 'sleeping' }))
    }
    if (attempt < 80) setTimeout(() => check(attempt + 1), 3000)
    else setState((s) => ({ ...s, status: 'gave_up' }))
  }, [])
  useEffect(() => { check(0); return () => { stopped.current = true } }, [check])
  return { ...state, retry: () => { stopped.current = false; check(0) } }
}

function Shell() {
  const { employee, toast } = useSession()
  const backend = useBackendReady()
  if (!backend.ready) return <><DemoStrip /><WarmUp {...backend} /></>
  return (
    <>
      <DemoStrip />
      {!employee ? <SignIn /> : (
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="chat" element={<Chat />} />
            <Route path="tickets" element={<Tickets />} />
            <Route path="library" element={<Library />} />
            <Route path="library/:docId" element={<DocViewer />} />
            <Route path="documents" element={<Navigate to="/library" replace />} />
            <Route path="insights" element={<Insights />} />
            <Route path="about" element={<About />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      )}
      {toast && <div className="toast" role="status"><CheckCircle2 size={16} />{toast}</div>}
    </>
  )
}

function DemoStrip() {
  return (
    <div className="demo-strip">
      <strong>College project demo.</strong> Nexora Technologies is a fictional company; policies and employee data are fictional.
    </div>
  )
}

export default function App() {
  return <SessionProvider><Shell /></SessionProvider>
}
