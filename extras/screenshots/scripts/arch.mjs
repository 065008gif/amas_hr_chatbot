import puppeteer from 'puppeteer-core'
const b = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: 'new' })
const p = await b.newPage(); await p.setViewport({ width: 1200, height: 760, deviceScaleFactor: 2 })
await p.goto('file:///home/ashok/hrbot/.cache/screens/arch.html'); await new Promise(r=>setTimeout(r,500))
await p.screenshot({ path: '/home/ashok/hrbot/report/img/architecture.png' }); await b.close()
