import { useEffect, useRef, useState } from 'react'
import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { ChevronLeft, ChevronRight, Download, ZoomIn, ZoomOut } from 'lucide-react'
import { pdfUrl } from '../lib/api.js'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl
const docs = new Map() // doc_id -> loading promise (each PDF is fetched once per visit)

function loadDoc(docId) {
  if (!docs.has(docId)) {
    const p = pdfjs.getDocument({ url: pdfUrl(docId) }).promise
    p.catch(() => docs.delete(docId))
    docs.set(docId, p)
  }
  return docs.get(docId)
}

/** Renders one page of a policy PDF, fitted to the panel width, with page navigation. */
export default function PdfViewer({ docId, page = 1, onPageChange, highlight }) {
  const stage = useRef(null)
  const canvas = useRef(null)
  const [pdf, setPdf] = useState(null)
  const [err, setErr] = useState(null)
  const [cur, setCur] = useState(page)
  const [zoom, setZoom] = useState(1)
  const [input, setInput] = useState(String(page))
  const [width, setWidth] = useState(0)
  const [busy, setBusy] = useState(true)

  useEffect(() => { setCur(page); setInput(String(page)) }, [page, docId])
  useEffect(() => {
    let live = true
    setPdf(null); setErr(null)
    loadDoc(docId).then((d) => live && setPdf(d)).catch(() => live && setErr('Could not load this document. Please try again.'))
    return () => { live = false }
  }, [docId])
  useEffect(() => {
    if (!stage.current) return undefined
    const ro = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width)))
    ro.observe(stage.current)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (!pdf || !width || !canvas.current) return undefined
    let task
    let live = true
    setBusy(true)
    pdf.getPage(Math.min(Math.max(1, cur), pdf.numPages)).then(async (p) => {
      if (!live) return
      const base = p.getViewport({ scale: 1 })
      const fit = Math.max(0.5, (width - 32) / base.width) * zoom
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      const vp = p.getViewport({ scale: fit * dpr })
      const c = canvas.current
      c.width = vp.width; c.height = vp.height
      c.style.width = `${vp.width / dpr}px`
      task = p.render({ canvasContext: c.getContext('2d'), viewport: vp })
      try { await task.promise } catch { /* cancelled */ }
      if (live) setBusy(false)
    })
    return () => { live = false; task?.cancel() }
  }, [pdf, cur, width, zoom])

  const go = (n) => {
    if (!pdf) return
    const p = Math.min(Math.max(1, n), pdf.numPages)
    setCur(p); setInput(String(p)); onPageChange?.(p)
  }

  return (
    <div className="pdf" style={{ flex: 1 }}>
      <div className="pdf-toolbar">
        <button className="btn btn-ghost icon-btn" onClick={() => go(cur - 1)} disabled={!pdf || cur <= 1} aria-label="Previous page"><ChevronLeft size={18} /></button>
        <form onSubmit={(e) => { e.preventDefault(); go(parseInt(input, 10) || 1) }} className="row" style={{ gap: '.35rem' }}>
          <label className="sr-only" htmlFor={`pg-${docId}`}>Page</label>
          <input id={`pg-${docId}`} className="input" value={input} inputMode="numeric" onChange={(e) => setInput(e.target.value.replace(/\D/g, ''))} />
          <span className="small muted">of {pdf?.numPages ?? '…'}</span>
        </form>
        <button className="btn btn-ghost icon-btn" onClick={() => go(cur + 1)} disabled={!pdf || cur >= (pdf?.numPages || 1)} aria-label="Next page"><ChevronRight size={18} /></button>
        <div className="spacer" />
        <button className="btn btn-ghost icon-btn" onClick={() => setZoom((z) => Math.max(0.6, z - 0.2))} aria-label="Zoom out"><ZoomOut size={17} /></button>
        <button className="btn btn-ghost icon-btn" onClick={() => setZoom((z) => Math.min(2.4, z + 0.2))} aria-label="Zoom in"><ZoomIn size={17} /></button>
        <a className="btn btn-ghost icon-btn" href={`${pdfUrl(docId)}#page=${cur}`} target="_blank" rel="noreferrer" aria-label="Open PDF in a new tab" title="Open PDF in a new tab"><Download size={17} /></a>
      </div>
      {highlight}
      <div className="pdf-stage" ref={stage}>
        {err ? <div className="alert danger" style={{ alignSelf: 'flex-start' }}>{err}</div> : (
          <div style={{ position: 'relative' }}>
            <canvas ref={canvas} aria-label={`Page ${cur} of the document`} role="img" style={{ opacity: busy ? 0.35 : 1, transition: 'opacity .2s' }} />
            {busy && <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}><div className="spinner" /></div>}
          </div>
        )}
      </div>
    </div>
  )
}
