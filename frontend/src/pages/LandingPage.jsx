/**
 * pages/LandingPage.jsx
 * Full-screen hero landing page — standalone layout (NO Sidebar/Topbar).
 * Animated CSS priority heatmap demo, project stats, and CTA.
 */

import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Zap, Eye, BarChart3, Radio, ChevronDown, Github } from 'lucide-react'
import Button from '../components/ui/Button'

/* ─── Animated priority heatmap demo (CSS only) ─────────────── */
const DEMO_REGIONS = [
  { id: 'face',   label: 'P1 · Face',       color: '#00FF87', style: { top: '22%', left: '32%', width: '24%', height: '35%' }, delay: '0s' },
  { id: 'text',   label: 'P2 · Text',        color: '#4ADE80', style: { top: '10%', left: '5%',  width: '22%', height: '12%' }, delay: '0.3s' },
  { id: 'motion', label: 'P3 · Motion',      color: '#F59E0B', style: { top: '50%', left: '60%', width: '20%', height: '18%' }, delay: '0.6s' },
  { id: 'obj',    label: 'P4 · Object',      color: '#818CF8', style: { top: '62%', left: '18%', width: '16%', height: '20%' }, delay: '0.9s' },
  { id: 'bg',     label: 'P5 · Background',  color: '#EF4444', style: { top: '0',   left: '0',   width: '100%', height: '100%', zIndex: -1 }, delay: '1.2s' },
]

function HeatmapDemo() {
  return (
    <div
      className="relative rounded-card overflow-hidden"
      style={{ width: '100%', aspectRatio: '16/9', background: 'rgba(15,20,38,0.8)', border: '1px solid rgba(79,70,229,0.3)' }}
    >
      {/* Simulated video-like background noise */}
      <div className="absolute inset-0 opacity-20"
        style={{ background: 'radial-gradient(ellipse at 40% 40%, rgba(79,70,229,0.3) 0%, transparent 60%)' }} />

      {/* Priority region overlays */}
      {DEMO_REGIONS.map(({ id, label, color, style, delay }) => (
        <div
          key={id}
          className="absolute rounded-sm"
          style={{
            ...style,
            background: `${color}22`,
            border: `1.5px solid ${color}80`,
            boxShadow: `0 0 16px ${color}30`,
            animation: `fadeIn 0.5s ease-out both`,
            animationDelay: delay,
          }}
        >
          {id !== 'bg' && (
            <span
              className="absolute top-1.5 left-1.5 text-xs font-mono px-1.5 py-0.5 rounded"
              style={{ background: `${color}22`, color, border: `1px solid ${color}40`, fontSize: 9, whiteSpace: 'nowrap' }}
            >
              {label}
            </span>
          )}
        </div>
      ))}

      {/* Scan line animation */}
      <div
        className="absolute left-0 right-0 h-0.5 pointer-events-none"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(79,70,229,0.6), transparent)', animation: 'scan 2.5s linear infinite' }}
      />

      {/* LIVE badge */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5 px-2 py-1 rounded-badge text-xs font-mono"
        style={{ background: 'rgba(0,255,135,0.12)', border: '1px solid rgba(0,255,135,0.3)', color: '#00FF87' }}>
        <span className="live-dot" />
        LIVE ANALYSIS
      </div>
    </div>
  )
}

/* ─── Stat item ────────────────────────────────────────────── */
function StatCard({ value, label, icon: Icon, color = '#818CF8' }) {
  return (
    <div className="flex flex-col items-center gap-1 px-6 py-4">
      <Icon size={20} style={{ color }} className="mb-1" />
      <div className="font-display text-2xl font-bold text-text-primary">{value}</div>
      <div className="text-xs text-text-muted text-center">{label}</div>
    </div>
  )
}

/* ─── Feature pill ─────────────────────────────────────────── */
function FeaturePill({ icon: Icon, text, color }) {
  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 rounded-badge text-xs font-medium"
      style={{ background: `${color}14`, border: `1px solid ${color}30`, color }}
    >
      <Icon size={12} />
      {text}
    </div>
  )
}

/* ─── Main page ─────────────────────────────────────────────── */
export default function LandingPage() {
  const navigate = useNavigate()
  const heroRef = useRef(null)

  /* Parallax tilt on hero on mouse move */
  useEffect(() => {
    const el = heroRef.current
    if (!el) return
    const handleMove = (e) => {
      const rect = el.getBoundingClientRect()
      const cx = (e.clientX - rect.left - rect.width / 2) / rect.width
      const cy = (e.clientY - rect.top  - rect.height / 2) / rect.height
      el.style.transform = `perspective(1000px) rotateY(${cx * 4}deg) rotateX(${-cy * 2}deg)`
    }
    const handleLeave = () => { el.style.transform = 'perspective(1000px) rotateY(0deg) rotateX(0deg)' }
    el.addEventListener('mousemove', handleMove)
    el.addEventListener('mouseleave', handleLeave)
    return () => { el.removeEventListener('mousemove', handleMove); el.removeEventListener('mouseleave', handleLeave) }
  }, [])

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: 'linear-gradient(135deg, #0A0E1A 0%, #0F1426 50%, #0D1235 100%)' }}
    >
      {/* ── Nav bar ── */}
      <header className="flex items-center justify-between px-8 py-5 border-b border-border-subtle">
        <div className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-btn flex items-center justify-center text-sm font-bold font-mono"
            style={{ background: 'linear-gradient(135deg, #4F46E5, #818CF8)', boxShadow: '0 0 16px rgba(79,70,229,0.4)' }}
          >
            SS
          </div>
          <span className="font-display font-semibold text-text-primary tracking-tight">SemanticStream</span>
          <span className="text-xs text-text-muted font-mono ml-1 hidden sm:inline">v1.0</span>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate('/research')}>
            Research
          </Button>
          <Button variant="ghost" size="sm" onClick={() => navigate('/dashboard')}>
            Dashboard
          </Button>
          <Button size="sm" onClick={() => navigate('/upload')} icon={<ArrowRight size={14} />}>
            Start Analyzing
          </Button>
        </div>
      </header>

      {/* ── Hero ── */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-16">
        {/* Pill badges */}
        <div className="flex flex-wrap justify-center gap-2 mb-8 animate-fade-in">
          <FeaturePill icon={Eye}     text="5-Tier Semantic Priority"       color="#00FF87" />
          <FeaturePill icon={Zap}     text="SPQI — Novel Quality Metric"    color="#818CF8" />
          <FeaturePill icon={Radio}   text="Live WebSocket Analysis"        color="#60A5FA" />
          <FeaturePill icon={BarChart3} text="3-Strategy Comparison"        color="#F59E0B" />
        </div>

        {/* Headline */}
        <h1 className="font-display text-5xl md:text-6xl font-bold text-center mb-4 animate-slide-up" style={{ lineHeight: 1.1 }}>
          <span className="text-text-primary">Compress Smarter.</span>
          <br />
          <span className="gradient-text">Protect What Matters.</span>
        </h1>
        <p className="text-lg text-text-muted text-center max-w-xl mb-10 animate-fade-in leading-relaxed" style={{ animationDelay: '0.2s' }}>
          SemanticStream uses AI-driven object detection to apply spatially non-uniform
          video compression — protecting faces and text while aggressively compressing
          unimportant backgrounds. Up to <strong className="text-data-green">48% bitrate savings</strong> with higher perceived quality.
        </p>

        {/* CTA buttons */}
        <div className="flex flex-wrap justify-center gap-4 mb-16 animate-fade-in" style={{ animationDelay: '0.3s' }}>
          <Button
            size="lg"
            onClick={() => navigate('/upload')}
            icon={<ArrowRight size={18} />}
            className="text-base px-8"
          >
            Analyze a Video
          </Button>
          <Button
            variant="ghost"
            size="lg"
            onClick={() => navigate('/live')}
            icon={<Radio size={18} />}
            className="text-base"
          >
            Try Live Camera
          </Button>
        </div>

        {/* Demo heatmap */}
        <div
          ref={heroRef}
          className="w-full max-w-2xl transition-transform duration-200 animate-fade-in"
          style={{ animationDelay: '0.5s', transitionTimingFunction: 'ease-out' }}
        >
          <HeatmapDemo />
          <p className="text-xs text-text-muted text-center mt-2 font-mono">
            Semantic priority heatmap — P1 (green) → P5 (red) encoding quality
          </p>
        </div>
      </main>

      {/* ── Stats row ── */}
      <section className="border-y border-border-subtle">
        <div className="flex flex-wrap justify-center divide-x divide-border-subtle">
          <StatCard value="5-Tier" label="Priority Hierarchy"  icon={Eye}      color="#00FF87" />
          <StatCard value="SPQI"   label="Novel Quality Metric" icon={BarChart3} color="#818CF8" />
          <StatCard value="~48%"   label="Avg. Bitrate Savings"  icon={Zap}      color="#F59E0B" />
          <StatCard value="<35ms"  label="Per-Frame Latency"     icon={Radio}    color="#60A5FA" />
        </div>
      </section>

      {/* ── Algorithm highlights ── */}
      <section className="max-w-5xl mx-auto px-6 py-16 w-full">
        <h2 className="font-display text-2xl font-bold text-center text-text-primary mb-10">
          Four Novel Research Contributions
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {[
            {
              num: '01', color: '#00FF87',
              title: '5-Tier Dynamic Priority Hierarchy',
              desc: 'Unlike binary ROI systems, SemanticStream dynamically re-ranks regions every frame using semantic class, detection confidence, optical flow, and temporal persistence.',
            },
            {
              num: '02', color: '#818CF8',
              title: 'SPQI — Semantic Perceptual Quality Index',
              desc: 'The first quality metric to weight SSIM measurements by semantic region importance. A face preserved perfectly scores HIGH under SPQI even if the background is compressed aggressively.',
            },
            {
              num: '03', color: '#F59E0B',
              title: 'Closed-Loop Semantic Rate Controller',
              desc: 'When P1-region SPQI drops below 0.75, the system automatically reallocates 5% of the P5 bitrate budget to P1 — maintaining face quality without exceeding total bandwidth.',
            },
            {
              num: '04', color: '#60A5FA',
              title: 'Confidence-Weighted Graceful Degradation',
              desc: 'When YOLO confidence drops (dark scenes, occlusion), the system falls back to optical flow magnitude as the priority signal. No published semantic streaming system handles detection failures.',
            },
          ].map(({ num, color, title, desc }) => (
            <div
              key={num}
              className="glass-card p-6 rounded-card transition-shadow duration-300 hover:shadow-card-hover"
            >
              <div className="font-mono text-xs mb-3" style={{ color }}>CONTRIBUTION {num}</div>
              <h3 className="font-display font-semibold text-text-primary mb-2 text-base">{title}</h3>
              <p className="text-sm text-text-muted leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-border-subtle px-8 py-6 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="text-xs text-text-muted">
          VIT Vellore · BITE314L Multimedia Systems · Fall 2026-27
          <span className="mx-2">·</span>
          Mayukh Banerjee · Shubham Kumar · Yashwant Sahoo
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/research')}
            className="text-xs text-text-muted hover:text-accent-light transition-colors"
          >
            Research Page
          </button>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-muted hover:text-accent-light transition-colors"
          >
            <Github size={16} />
          </a>
        </div>
      </footer>
    </div>
  )
}
