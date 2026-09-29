// Before/after screenshots of the five main pages, desktop + phone. Usage: TAG=before node shots3.mjs
import puppeteer from 'puppeteer-core'
import fs from 'fs'
const BASE = process.env.BASE || 'http://localhost:5173'
const TAG = process.env.TAG || 'before'
const OUT = `/home/ashok/hrbot/.cache/screens/${TAG}`
const FX = process.env.FX || new URL('../fixtures', import.meta.url).pathname
fs.mkdirSync(OUT, { recursive: true })
const emp = { employee_id: 'NXR100056', name: 'Arjun Verma', grade: 'L4', designation: 'Senior Software Engineer', location: 'Noida' }
const qs = ['What is the hotel limit for an L5 staying in Mumbai?', 'What is the notice period if I resign at L5?',
  'My manager keeps making comments about my appearance and I feel unsafe', 'Does Nexora pay for egg freezing?']
const chat = qs.flatMap((q, i) => [{ id: `u${i}`, role: 'user', content: q },
  { id: `a${i}`, role: 'assistant', response: JSON.parse(fs.readFileSync(`${FX}/${i + 1}.json`)) }])
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: 'new',
  userDataDir: `/home/ashok/hrbot/.cache/screens/chrome-profile`, args: ['--no-first-run', '--no-default-browser-check'] })
const page = await browser.newPage()
page.on('pageerror', (e) => console.log('PAGE ERROR', e.message))
page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE', m.text()) })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
await page.goto(BASE, { waitUntil: 'networkidle0' })
await page.evaluate((e, c) => { localStorage.clear(); localStorage.setItem('nxr.employee', JSON.stringify(e)); localStorage.setItem('nxr.chat.NXR100056', JSON.stringify(c)); localStorage.setItem('nxr.profile.NXR100056', JSON.stringify({ grade: 'L4', location: 'Noida' })) }, emp, chat)
for (const [vw, w, h] of [['desktop', 1440, 900], ['phone', 390, 844]]) {
  await page.setViewport({ width: w, height: h, deviceScaleFactor: vw === 'phone' ? 2 : 1 })
  for (const [name, path] of [['home', '/'], ['chat', '/chat'], ['tickets', '/tickets'], ['library', '/library'], ['insights', '/insights']]) {
    await page.goto(BASE + path, { waitUntil: 'networkidle0' }); await wait(900)
    if (name === 'chat') {
      // first answer (with conflict) in view, then the end of the conversation
      await page.evaluate(() => { const m = document.querySelector('.messages'); m.style.scrollBehavior = 'auto'; const el = document.querySelectorAll('.msg.user')[0]; m.scrollTop = el.offsetTop - m.offsetTop - 8 }); await wait(400)
      await page.screenshot({ path: `${OUT}/${vw}-chat-1.png` })
      await page.evaluate(() => { const m = document.querySelector('.messages'); m.style.scrollBehavior = 'auto'; m.scrollTop = m.scrollHeight }); await wait(400)
      await page.screenshot({ path: `${OUT}/${vw}-chat-2.png` })
    } else {
      await page.screenshot({ path: `${OUT}/${vw}-${name}.png`, fullPage: vw === 'phone' })
    }
  }
}
await browser.close()
console.log('saved to', OUT, fs.readdirSync(OUT).join(' '))
