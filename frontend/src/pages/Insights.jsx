import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { BarChart3, Clock, Database, Lock, MessagesSquare, RefreshCw, Table2, Target } from 'lucide-react'
import { api } from '../lib/api.js'
import { Empty, Skeleton } from '../components/ui.jsx'

// Accent palette (600 steps: each is at least 3:1 against white; validated with the dataviz palette checker).
// Single-series charts use one hue each; "How questions were handled" colours each bar by its route
// (same meaning as the chat badges), and every bar also carries a text label, so colour is never the only cue.
const HUE = { indigo: '#4f46e5', violet: '#7c3aed', emerald: '#059669', amber: '#d97706', rose: '#e11d48', sky: '#0284c7' }
const ROUTE_HUE = { answer: HUE.emerald, not_found: HUE.sky, escalate: HUE.rose, tool: HUE.indigo, refused: HUE.violet, clarify: HUE.amber, error: HUE.amber }
const AXIS = { fontSize: 12, fill: '#5f5c7e' }
const ROUTE_LABEL = { answer: 'Answered', not_found: 'Not found', escalate: 'Escalated to HR', tool: 'Tool (balance, tickets)',
  refused: 'Declined', clarify: 'Asked to clarify', error: 'Service busy' }

function ChartTip({ active, payload, unit = 'questions' }) {
  if (!active || !payload?.length) return null
  const p = payload[0]
  return (
    <div className="card" style={{ padding: '.45rem .65rem', fontSize: '.82rem', boxShadow: 'var(--shadow)' }}>
      <div style={{ fontWeight: 600, color: 'var(--ink)' }}>{p.payload.name}</div>
      <div className="muted">{p.value} {unit}</div>
    </div>
  )
}

function VizCard({ title, note, data, horizontal = true, height, color = HUE.indigo }) {
  const [table, setTable] = useState(false)
  const h = height || Math.max(160, data.length * 34 + 30)
  return (
    <section className="card viz-card">
      <div className="card-head">
        <h2>{title}</h2><span className="spacer" />
        <button className="btn btn-ghost btn-sm" onClick={() => setTable((t) => !t)} aria-pressed={table}>{table ? <BarChart3 size={14} /> : <Table2 size={14} />}{table ? 'Chart' : 'Table'}</button>
      </div>
      <div className="card-body">
        {!data.length ? <Empty icon={BarChart3} title="No data yet">Ask Nia a few questions and refresh.</Empty> : table ? (
          <table className="table"><thead><tr><th>{horizontal ? 'Category' : 'Day'}</th><th style={{ textAlign: 'right' }}>Questions</th></tr></thead>
            <tbody>{data.map((d) => <tr key={d.name}><td>{d.name}</td><td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{d.n}</td></tr>)}</tbody></table>
        ) : (
          <div style={{ width: '100%', height: h }}>
            <ResponsiveContainer>
              {horizontal ? (
                <BarChart data={data} layout="vertical" margin={{ top: 4, right: 36, bottom: 4, left: 4 }} barCategoryGap={6}>
                  <CartesianGrid horizontal={false} stroke="#ebe7fb" />
                  <XAxis type="number" allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={150} tick={{ ...AXIS, fill: '#3b3a58' }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTip />} cursor={{ fill: 'rgba(124,58,237,.06)' }} />
                  <Bar dataKey="n" fill={color} radius={[0, 4, 4, 0]} maxBarSize={22} isAnimationActive={false}>
                    {data.map((d) => <Cell key={d.name} fill={d.color || color} />)}
                    <LabelList dataKey="n" position="right" style={{ fontSize: 12, fill: '#1e1b4b', fontWeight: 650 }} />
                  </Bar>
                </BarChart>
              ) : (
                <BarChart data={data} margin={{ top: 16, right: 8, bottom: 4, left: -16 }} barCategoryGap={4}>
                  <CartesianGrid vertical={false} stroke="#ebe7fb" />
                  <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTip />} cursor={{ fill: 'rgba(124,58,237,.06)' }} />
                  <Bar dataKey="n" fill={color} radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false}>
                    <LabelList dataKey="n" position="top" style={{ fontSize: 12, fill: '#1e1b4b', fontWeight: 650 }} />
                  </Bar>
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        )}
        {note && <p className="viz-note" style={{ marginTop: '.5rem' }}>{note}</p>}
      </div>
    </section>
  )
}

export default function Insights() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  const load = () => { setErr(null); api('/insights').then(setD).catch((e) => setErr(e.message)) }
  useEffect(load, [])

  const policyQs = d ? d.by_route.filter((r) => ['answer', 'not_found', 'clarify'].includes(r.route)).reduce((a, r) => a + r.n, 0) : 0
  const answered = d?.by_route.find((r) => r.route === 'answer')?.n || 0
  const kpis = d ? [
    { k: 'Questions handled', Icon: MessagesSquare, c: 'c-indigo', v: d.total_questions, d: `${d.repeat_questions} asked more than once` },
    { k: 'Answer rate', Icon: Target, c: 'c-emerald', v: policyQs ? `${Math.round((answered / policyQs) * 100)}%` : '–', d: 'answered with sources, of answered + not found + clarify' },
    { k: 'Cache hit rate', Icon: Database, c: 'c-sky', v: `${Math.round((d.cache_hit_rate || 0) * 100)}%`, d: 'repeat questions cost no model quota' },
    { k: 'Avg response time', Icon: Clock, c: 'c-amber', v: d.avg_latency_ms ? `${(d.avg_latency_ms / 1000).toFixed(1)} s` : '–', d: 'excluding cached answers' },
  ] : []

  return (
    <div className="content fade-in">
      <div className="page-head">
        <div><h1>HR Insights</h1><p>What employees ask Nia, from anonymised usage logs.</p></div>
        <span className="spacer" /><span className="badge vio">Demo admin view</span>
        <button className="btn btn-secondary btn-sm" onClick={load}><RefreshCw size={14} />Refresh</button>
      </div>
      <div className="alert info" style={{ marginBottom: '1.25rem' }}>
        <Lock size={16} />
        <div>Aggregates only. Nia does not store message text: each question is logged as its route, topic, response time, token count and a one-way hash. In a real deployment this page would be restricted to HR administrators.</div>
      </div>
      {err && <div className="alert danger">{err}</div>}
      {!d && !err && <div className="kpi-row">{[0, 1, 2, 3].map((i) => <div key={i} className="card stat"><Skeleton h={12} w="50%" /><Skeleton h={30} w="40%" style={{ marginTop: 10 }} /></div>)}</div>}
      {d && (
        <>
          <div className="kpi-row">
            {kpis.map((x) => <div key={x.k} className={`card stat ${x.c}`}><div className="k"><span className="stat-ic" aria-hidden="true"><x.Icon size={17} /></span>{x.k}</div><div className="v">{x.v}</div><div className="d">{x.d}</div></div>)}
          </div>
          <div className="grid grid-2" style={{ marginTop: '1.25rem' }}>
            <VizCard title="Questions by topic" color={HUE.indigo} data={d.by_topic.map((t) => ({ name: t.topic, n: t.n }))} note="Topic = the policy document of the best-matching source." />
            <VizCard title="How questions were handled" data={d.by_route.map((r) => ({ name: ROUTE_LABEL[r.route] || r.route, n: r.n, color: ROUTE_HUE[r.route] || HUE.violet }))} />
            <VizCard title="Top unanswered topics" color={HUE.amber} data={d.unanswered_topics.map((t) => ({ name: t.topic, n: t.n }))} note="Candidates for new policy content or FAQs." />
            <VizCard title="Questions per day" color={HUE.sky} horizontal={false} height={220} data={[...d.daily].reverse().map((x) => ({ name: x.day.slice(5), n: x.n }))} />
          </div>
        </>
      )}
    </div>
  )
}
