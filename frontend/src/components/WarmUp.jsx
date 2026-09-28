import { Coffee, RefreshCw, ServerCrash } from 'lucide-react'

export default function WarmUp({ status, attempts, error, retry }) {
  const pct = Math.min(95, 8 + attempts * 4)
  const failed = status === 'gave_up' || status === 'error'
  return (
    <div className="center-screen">
      <div className="warm card card-pad fade-in" role="status" aria-live="polite">
        <div className="pulse">{failed ? <ServerCrash size={28} /> : <Coffee size={28} />}</div>
        <h1 style={{ fontSize: '1.3rem' }}>{failed ? "The HR assistant didn't wake up" : 'Waking up the HR assistant'}</h1>
        <p className="muted" style={{ marginTop: '.5rem' }}>
          {failed
            ? (error || 'The free server did not respond. It may be restarting. Please try again.')
            : 'The demo runs on free serverless hosting. After a quiet period the first request starts a fresh instance, which loads the policy index and search models. This can take up to about a minute; after that, answers take a few seconds.'}
        </p>
        {!failed && <div className="progress" aria-hidden="true"><span style={{ width: `${pct}%` }} /></div>}
        {!failed && <div className="tiny muted">{status === 'sleeping' ? 'Starting the server…' : status === 'connecting' ? 'Starting the assistant and loading search models…' : 'Loading search models…'}</div>}
        {failed && <button className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={retry}><RefreshCw size={16} />Try again</button>}
      </div>
    </div>
  )
}
