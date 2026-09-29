import puppeteer from 'puppeteer-core'
const BASE = process.env.BASE || 'http://localhost:5173'
const OUT = process.env.OUT || '/home/ashok/hrbot/.cache/screens'
const emp = { employee_id: 'NXR100056', name: 'Arjun Verma', grade: 'L4', designation: 'Senior Software Engineer', location: 'Noida' }
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: 'new',
  userDataDir: `${OUT}/chrome-profile`, args: ['--no-first-run', '--no-default-browser-check'] })
const page = await browser.newPage()
const shot = async (name, w = 1440, h = 900) => { await page.setViewport({ width: w, height: h }); await new Promise(r => setTimeout(r, 700)); await page.screenshot({ path: `${OUT}/${name}.png` }) }
page.on('pageerror', e => console.log('PAGE ERROR', e.message))
page.on('console', m => { if (m.type() === 'error') console.log('CONSOLE', m.text()) })
await page.setViewport({ width: 1440, height: 900 })
await page.goto(BASE, { waitUntil: 'networkidle0' })
await shot('01-signin')
await page.evaluate((e) => { localStorage.clear(); localStorage.setItem('nxr.employee', JSON.stringify(e)) }, emp)
await page.goto(BASE, { waitUntil: 'networkidle0' }); await shot('02-home')
await page.goto(BASE + '/chat', { waitUntil: 'networkidle0' }); await shot('03-chat-empty')
await page.type('#msg', 'What is the hotel limit for an L5 staying in Mumbai?')
await page.keyboard.press('Enter')
await page.waitForSelector('.chip.cite', { timeout: 90000 })
await shot('04-chat-answer')
await page.click('.chip.cite'); await new Promise(r => setTimeout(r, 2500)); await shot('05-chat-citation')
await page.goto(BASE + '/tickets', { waitUntil: 'networkidle0' }); await shot('06-tickets')
await page.goto(BASE + '/library', { waitUntil: 'networkidle0' }); await page.type('#lib-q', 'gratuity'); await shot('07-library')
await page.goto(BASE + '/library/005?page=7', { waitUntil: 'networkidle0' }); await new Promise(r => setTimeout(r, 2000)); await shot('08-viewer')
await page.goto(BASE + '/insights', { waitUntil: 'networkidle0' }); await shot('09-insights')
await page.goto(BASE + '/about', { waitUntil: 'networkidle0' }); await shot('10-about')
await page.goto(BASE + '/', { waitUntil: 'networkidle0' }); await shot('11-home-phone', 390, 844)
await page.goto(BASE + '/chat', { waitUntil: 'networkidle0' }); await shot('12-chat-phone', 390, 844)
await browser.close()
console.log('done')
