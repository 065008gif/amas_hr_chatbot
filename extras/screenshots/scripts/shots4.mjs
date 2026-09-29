import puppeteer from 'puppeteer-core'
const BASE='http://localhost:5173', OUT='/home/ashok/hrbot/.cache/screens/after'
const emp = { employee_id: 'NXR100056', name: 'Arjun Verma', grade: 'L4', designation: 'Senior Software Engineer', location: 'Noida' }
const b = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: 'new', userDataDir: '/home/ashok/hrbot/.cache/screens/chrome-profile' })
const p = await b.newPage(); p.on('pageerror', e => console.log('PAGE ERROR', e.message))
await p.setViewport({ width: 1440, height: 900 })
await p.goto(BASE, { waitUntil: 'networkidle0' }); await p.evaluate(() => localStorage.clear())
await p.goto(BASE, { waitUntil: 'networkidle0' }); await new Promise(r => setTimeout(r, 800)); await p.screenshot({ path: `${OUT}/x-signin.png` })
await p.evaluate((e) => localStorage.setItem('nxr.employee', JSON.stringify(e)), emp)
for (const [n, path] of [['x-chat-empty', '/chat'], ['x-about', '/about'], ['x-viewer', '/library/005?page=7']]) {
  await p.goto(BASE + path, { waitUntil: 'networkidle0' }); await new Promise(r => setTimeout(r, 1500)); await p.screenshot({ path: `${OUT}/${n}.png` }) }
await b.close()
