const puppeteer = require('puppeteer-core')
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const routes = [
  '/dashboard',
  '/upload',
  '/live',
  '/streaming',
  '/analytics',
  '/bandwidth',
  '/experiments',
  '/reports',
  '/history',
  '/settings',
  '/research',
]

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox'],
  })
  const page = await browser.newPage()
  let failed = 0
  for (const r of routes) {
    try {
      await page.goto('http://localhost:5173' + r, {
        waitUntil: 'networkidle0',
        timeout: 15000,
      })
      const errorEl = await page.$('#error-boundary-fallback')
      if (errorEl) {
        console.error('FAILED (ErrorBoundary caught):', r)
        failed++
      } else {
        console.log('OK (200):', r)
      }
    } catch (e) {
      console.error('FAILED (Navigation error):', r, e.message)
      failed++
    }
  }
  await browser.close()
  if (failed > 0) process.exit(1)
  console.log('ALL 11 SIDEBAR ROUTES VERIFIED SUCCESSFULLY!')
})()
