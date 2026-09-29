import puppeteer from 'puppeteer-core'
const OUT='/home/ashok/hrbot/.cache/screens', BASE='http://localhost:5173'
const b = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: 'new', userDataDir: `${OUT}/chrome-profile` })
const p = await b.newPage(); p.on('pageerror', e => console.log('PAGE ERROR', e.message))
const shot = async (n, w, h) => { await p.setViewport({ width: w, height: h }); await new Promise(r => setTimeout(r, 900)); await p.screenshot({ path: `${OUT}/${n}.png` }) }
for (const [path, name, w, h] of [['/tickets?id=NXR-HR-2026-000136','13-ticket-detail',1440,900],['/', '14-home-desktop',1440,900],['/', '15-home-phone',390,844],['/library/005?page=7','16-viewer-phone',390,844],['/chat','17-chat-phone',390,844]]) {
  await p.setViewport({ width: w, height: h }); await p.goto(BASE + path, { waitUntil: 'networkidle0' }); await shot(name, w, h) }
await b.close(); console.log('done')
