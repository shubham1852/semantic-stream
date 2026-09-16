const puppeteer = require('puppeteer-core')
const path = require('path')
const fs = require('fs')

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'

const executablePath = fs.existsSync(CHROME_PATH) ? CHROME_PATH : EDGE_PATH
const OUTPUT_DIR = path.resolve(__dirname, '../../docs/screenshots')

if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true })
}

const EXPERIMENT_RESULTS = {
  experiment_id: 'ac685aa8-6f4e-4f80-aae3-02a76bf7ce38',
  status: 'done',
  bandwidth_profile: 'broadband',
  strategies: {
    uniform_abr: {
      strategy: 'uniform_abr',
      avg_spqi: 0.7313,
      avg_ssim: 0.7993,
      avg_bitrate_mbps: 2.82,
      face_ssim: 0.7904,
      bg_ssim: 0.8264,
      encode_time_ms: 1173,
      sees_score: 1.61,
      bitrate_reduction_pct: 0,
    },
    static_roi: {
      strategy: 'static_roi',
      avg_spqi: 0.8182,
      avg_ssim: 0.8607,
      avg_bitrate_mbps: 2.04,
      face_ssim: 0.8911,
      bg_ssim: 0.8086,
      encode_time_ms: 1396,
      sees_score: 22.25,
      bitrate_reduction_pct: 24.59,
    },
    semanticstream: {
      strategy: 'semanticstream',
      avg_spqi: 0.9209,
      avg_ssim: 0.9494,
      avg_bitrate_mbps: 1.59,
      face_ssim: 0.9825,
      bg_ssim: 0.8241,
      encode_time_ms: 4182,
      sees_score: 68.03,
      bitrate_reduction_pct: 41.99,
    },
  },
  winner: 'semanticstream',
}

async function capture() {
  console.log(`Using browser: ${executablePath}`)
  const browser = await puppeteer.launch({
    executablePath,
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu',
      '--window-size=1440,900',
    ],
    defaultViewport: {
      width: 1440,
      height: 900,
      deviceScaleFactor: 2,
    },
  })

  try {
    const page = await browser.newPage()

    // ── 1. Dashboard ──────────────────────────────────────────────────────────
    console.log('Capturing 01-dashboard.png...')
    await page.goto('http://localhost:5173/dashboard', { waitUntil: 'networkidle0', timeout: 30000 })
    await page.waitForSelector('h2')
    // Wait an extra second for fetch(/api/v1/demo/status) to render System Status cards
    await new Promise((r) => setTimeout(r, 2000))
    await page.screenshot({
      path: path.join(OUTPUT_DIR, '01-dashboard.png'),
      fullPage: false,
    })
    console.log('Saved 01-dashboard.png')

    // ── 2. Results Player ─────────────────────────────────────────────────────
    console.log('Capturing 02-results-player.png...')
    await page.goto('http://localhost:5173/results/b64157b2-5590-4590-b277-069eb28cfe4a', {
      waitUntil: 'networkidle0',
      timeout: 30000,
    })
    await page.waitForSelector('video')
    await new Promise((r) => setTimeout(r, 2500))
    await page.screenshot({
      path: path.join(OUTPUT_DIR, '02-results-player.png'),
      fullPage: false,
    })
    console.log('Saved 02-results-player.png')

    // ── 3. Live Camera ────────────────────────────────────────────────────────
    console.log('Capturing 03-live-camera.png...')
    await page.goto('http://localhost:5173/live', { waitUntil: 'networkidle0', timeout: 30000 })
    await new Promise((r) => setTimeout(r, 2000))
    await page.screenshot({
      path: path.join(OUTPUT_DIR, '03-live-camera.png'),
      fullPage: false,
    })
    console.log('Saved 03-live-camera.png')

    // ── 4. Experiments Workbench ──────────────────────────────────────────────
    console.log('Capturing 04-experiment.png...')
    await page.goto('http://localhost:5173/experiments', { waitUntil: 'networkidle0', timeout: 30000 })
    // Populate the experiment store so completed 3-strategy comparison cards and charts render
    await page.evaluate((data) => {
      // In zustand or DOM: dispatch or trigger done state
      const stateStr = localStorage.getItem('semanticstream_store')
      try {
        const parsed = stateStr ? JSON.parse(stateStr) : { state: {} }
        parsed.state.experiment = {
          experimentId: data.experiment_id,
          status: 'done',
          results: data.strategies,
          winner: data.winner,
          config: {
            videoId: 'fe3f2cf1-b969-4f6a-a743-9cb53ab0c0e5',
            strategies: ['uniform_abr', 'static_roi', 'semanticstream'],
            bandwidthProfile: 'broadband',
          },
        }
        localStorage.setItem('semanticstream_store', JSON.stringify(parsed))
      } catch (e) {
        console.error(e)
      }
    }, EXPERIMENT_RESULTS)

    // Reload with populated store
    await page.goto('http://localhost:5173/experiments', { waitUntil: 'networkidle0', timeout: 30000 })
    await new Promise((r) => setTimeout(r, 2500))
    await page.screenshot({
      path: path.join(OUTPUT_DIR, '04-experiment.png'),
      fullPage: false,
    })
    console.log('Saved 04-experiment.png')

    // ── 5. Research Page ──────────────────────────────────────────────────────
    console.log('Capturing 05-research.png...')
    await page.goto('http://localhost:5173/research', { waitUntil: 'networkidle0', timeout: 30000 })
    await new Promise((r) => setTimeout(r, 3000))
    await page.screenshot({
      path: path.join(OUTPUT_DIR, '05-research.png'),
      fullPage: false,
    })
    console.log('Saved 05-research.png')

    console.log('All 5 screenshots captured successfully!')
  } finally {
    await browser.close()
  }
}

capture().catch((err) => {
  console.error('Screenshot capture failed:', err)
  process.exit(1)
})
