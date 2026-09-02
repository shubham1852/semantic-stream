/**
 * pages/ResearchPage.jsx
 * About / Research page — KaTeX-rendered SPQI and SEES formulas,
 * architecture overview, 5-tier hierarchy table, 4 novel contributions,
 * and 17-reference literature list.
 */

import 'katex/dist/katex.min.css'
import katex from 'katex'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Github, BookOpen, FlaskConical, Users, Award, FileText } from 'lucide-react'
import PageShell from '../components/layout/PageShell'
import Card from '../components/ui/Card'
import { TierBadge } from '../components/ui/Badge'

/* ─── KaTeX renderer ─────────────────────────────────────── */
function Formula({ latex, display = true }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(latex, { displayMode: display, throwOnError: false })
    } catch {
      return `<code>${latex}</code>`
    }
  }, [latex, display])
  return (
    <div
      className="overflow-x-auto py-2"
      style={{ color: '#F0F0FF' }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

/* ─── 5-Tier table data ──────────────────────────────────── */
const TIERS = [
  { tier: 'P1', label: 'Face / Person',   color: '#00FF87', w: '1.0', qp: 18, trigger: 'YOLO: person class', desc: 'Highest visual attention — always protected' },
  { tier: 'P2', label: 'Text Overlay',    color: '#4ADE80', w: '0.8', qp: 22, trigger: 'Text detector / flag', desc: 'Readable content — legibility preserved' },
  { tier: 'P3', label: 'Motion Region',   color: '#F59E0B', w: '0.6', qp: 26, trigger: 'Optical flow > 2px', desc: 'Eye tracks motion — mid quality' },
  { tier: 'P4', label: 'Detected Object', color: '#818CF8', w: '0.4', qp: 32, trigger: 'YOLO: other classes', desc: 'Background objects — reduced quality' },
  { tier: 'P5', label: 'Background',      color: '#EF4444', w: '0.1', qp: 40, trigger: 'No detection', desc: 'Maximum compression — perceptually invisible' },
]

/* ─── References ─────────────────────────────────────────── */
const REFERENCES = [
  '[1] Yin, X., et al. (2015). BOLA: Near-Optimal Bitrate Adaptation for Online Videos. IEEE INFOCOM.',
  '[2] Wang, Z., et al. (2004). Image Quality Assessment: From Error Visibility to Structural Similarity. IEEE TIP, 13(4), 600–612.',
  '[3] Redmon, J., & Farhadi, A. (2018). YOLOv3: An Incremental Improvement. arXiv:1804.02767.',
  '[4] Bochkovskiy, A., Wang, C.-Y., & Liao, H.-Y. M. (2020). YOLOv4: Optimal Speed and Accuracy of Object Detection. arXiv:2004.10934.',
  '[5] Jocher, G., et al. (2023). Ultralytics YOLOv8. GitHub. https://github.com/ultralytics/ultralytics.',
  '[6] De Cock, J., et al. (2016). A Subjective Quality Assessment Study on 360° Video. IEEE ICME.',
  '[7] Wamser, F., et al. (2016). YoMo: A YouTube Application Comfort Monitoring Tool. IEEE IFIP NOMS.',
  '[8] Ghadiyaram, D., et al. (2019). Large-Scale Study of Perceptual Video Quality. IEEE TIP, 28(2), 612–627.',
  '[9] Li, Z., et al. (2016). Toward a Practical Perceptual Video Quality Metric. Netflix Tech Blog.',
  '[10] Mok, R. K. P., et al. (2011). Measuring the Quality of Experience of HTTP Video Streaming. IEEE IM.',
  '[11] Pantos, R. (Ed.). (2017). HTTP Live Streaming. IETF RFC 8216.',
  '[12] Huang, T.-Y., et al. (2014). BOLA: Buffer Occupancy Based Lyapunov Algorithm for Adaptive Streaming. ACM MMSys.',
  '[13] Krishnamoorthi, V., et al. (2017). SARA: Segment Aware Rate Adaptation for Dynamic Adaptive Streaming. IEEE ICC.',
  '[14] Kua, J., et al. (2017). A Survey of Rate Adaptation Techniques for Dynamic Adaptive HTTP Streaming. IEEE COMST.',
  '[15] Li, B., et al. (2014). Probe and Adapt: Rate Adaptation for HTTP Video Streaming at Scale. IEEE JSAC, 32(4), 719–733.',
  '[16] Bentaleb, A., et al. (2018). A Survey on Bitrate Adaptation Schemes for Streaming Media over HTTP. IEEE COMST.',
  '[17] Dobrian, F., et al. (2011). Understanding the Impact of Video Quality on User Engagement. ACM SIGCOMM.',
]

/* ─── Contribution card ──────────────────────────────────── */
function ContributionCard({ num, title, color, children }) {
  return (
    <div className="glass-card rounded-card p-6">
      <div className="font-mono text-xs mb-2" style={{ color }}>CONTRIBUTION {num}</div>
      <h3 className="font-display font-semibold text-text-primary mb-3">{title}</h3>
      <p className="text-sm text-text-muted leading-relaxed">{children}</p>
    </div>
  )
}

/* ─── Architecture layers diagram (SVG) ─────────────────── */
function ArchitectureDiagram() {
  const layers = [
    { label: 'Video Input',          color: '#60A5FA', desc: 'MP4 / Live Camera' },
    { label: 'YOLO Detection',       color: '#818CF8', desc: 'YOLOv8n ONNX → Bboxes + Classes' },
    { label: 'Priority Engine',      color: '#00FF87', desc: '5-Tier Map + Confidence Weighting' },
    { label: 'Temporal Propagation', color: '#4ADE80', desc: 'EMA Smoothing + SEES Savings' },
    { label: 'QP Assignment',        color: '#F59E0B', desc: 'BOLA Rate Control → QP Matrix' },
    { label: 'FFmpeg Encoder',       color: '#EF4444', desc: 'libx264 Spatial QP Injection' },
    { label: 'HLS Output + SPQI',    color: '#60A5FA', desc: 'Adaptive Stream + Quality Report' },
  ]
  return (
    <div className="w-full space-y-1.5">
      {layers.map(({ label, color, desc }, i) => (
        <div key={i} className="flex items-center gap-3">
          <div
            className="w-36 text-right text-xs font-mono font-semibold shrink-0"
            style={{ color }}
          >
            {i + 1}. {label}
          </div>
          <div
            className="flex-1 h-8 rounded-btn flex items-center px-3 text-xs text-text-muted"
            style={{ background: `${color}12`, border: `1px solid ${color}25` }}
          >
            {desc}
          </div>
          {i < layers.length - 1 && (
            <svg width="12" height="12" className="shrink-0 text-text-muted rotate-90" viewBox="0 0 12 12">
              <path d="M6 2v8M3 7l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
            </svg>
          )}
        </div>
      ))}
    </div>
  )
}

/* ─── Main ─────────────────────────────────────────────────── */
export default function ResearchPage() {
  return (
    <PageShell>
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Project header */}
        <Card className="p-8">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-mono text-accent-light mb-2">BITE314L · Multimedia Systems · VIT Vellore · Fall 2026-27</div>
              <h1 className="font-display text-3xl font-bold text-text-primary mb-2">
                SemanticStream
              </h1>
              <p className="text-lg text-text-muted max-w-xl leading-relaxed">
                Semantic-Aware Adaptive Video Streaming Framework with Bandwidth-Aware Region Priority Encoding
              </p>
            </div>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-muted hover:text-accent-light transition-colors"
            >
              <Github size={24} />
            </a>
          </div>

          {/* Team */}
          <div className="mt-6 pt-6 border-t border-border-subtle">
            <div className="flex items-center gap-2 text-sm text-text-muted mb-3">
              <Users size={14} className="text-accent-light" />
              <span className="font-medium text-text-primary">Team Members</span>
              <span className="mx-2">·</span>
              <span>Faculty Guide: Dr. Balasubramani M, Dept. of Information Technology</span>
            </div>
            <div className="flex flex-wrap gap-3">
              {[
                { name: 'Mayukh Banerjee', id: '23BIT0061' },
                { name: 'Shubham Kumar',   id: '23BIT0079' },
                { name: 'Yashwant Sahoo',  id: '23BIT0115' },
              ].map(({ name, id }) => (
                <div
                  key={id}
                  className="px-3 py-1.5 rounded-badge text-sm"
                  style={{ background: 'rgba(79,70,229,0.1)', border: '1px solid rgba(79,70,229,0.25)' }}
                >
                  <span className="text-text-primary font-medium">{name}</span>
                  <span className="text-text-muted ml-2 font-mono text-xs">{id}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Novel Contributions */}
        <div>
          <h2 className="font-display text-xl font-bold text-text-primary mb-4 flex items-center gap-2">
            <Award size={20} className="text-data-amber" />
            Novel Research Contributions
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ContributionCard num="01" title="5-Tier Dynamic Priority Hierarchy" color="#00FF87">
              Unlike binary ROI systems, SemanticStream dynamically re-ranks regions every frame
              using semantic class, detection confidence, optical flow magnitude, and temporal
              persistence. Tier membership changes per frame — this is not a static annotation system.
            </ContributionCard>
            <ContributionCard num="02" title="SPQI — Semantic Perceptual Quality Index" color="#818CF8">
              The first quality metric to weight SSIM measurements by semantic region importance.
              A frame where a face is perfectly preserved but the background is compressed aggressively
              scores HIGH under SPQI but MEDIOCRE under standard SSIM — correctly reflecting human perception.
            </ContributionCard>
            <ContributionCard num="03" title="Closed-Loop Semantic Rate Controller" color="#F59E0B">
              After encoding each segment, the system measures P1-region SPQI. If it falls below 0.75,
              5% of the P5 bitrate budget is reallocated to P1 within the same total bandwidth envelope.
              No published ABR or ROI system implements this closed-loop semantic feedback.
            </ContributionCard>
            <ContributionCard num="04" title="Confidence-Weighted Graceful Degradation" color="#60A5FA">
              When YOLO detection confidence drops below 0.5 (dark scenes, motion blur, occlusion),
              SemanticStream downgrades the region to P3 and switches to optical flow as the priority
              signal. This makes the system robust — not just high-performing under ideal conditions.
            </ContributionCard>
          </div>
        </div>

        {/* SPQI Formula */}
        <Card className="p-6">
          <h2 className="font-display text-lg font-bold text-text-primary mb-2 flex items-center gap-2">
            <FlaskConical size={18} className="text-accent-light" />
            SPQI — Semantic Perceptual Quality Index
          </h2>
          <p className="text-sm text-text-muted mb-4">
            A semantically-weighted full-reference video quality metric. Computes SSIM per detected
            region and weights it by semantic priority score.
          </p>
          <div className="rounded-btn p-4" style={{ background: 'rgba(15,20,38,0.8)', border: '1px solid rgba(79,70,229,0.2)' }}>
            <Formula latex={`\\text{SPQI} = \\frac{\\sum_{i} w_i \\cdot \\text{SSIM}(R_i,\\, R_i')}{\\sum_{i} w_i}`} />
          </div>
          <div className="mt-3 text-sm text-text-muted space-y-1">
            <p>where <em className="text-text-primary">i</em> indexes each detected semantic region,</p>
            <p><em className="text-text-primary">w_i</em> ∈ {'{'} P1: 1.0, P2: 0.8, P3: 0.6, P4: 0.4, P5: 0.1 {'}'} is the region's priority weight,</p>
            <p><em className="text-text-primary">SSIM(R_i, R_i')</em> is the structural similarity between the original and compressed pixels in region <em>i</em>.</p>
          </div>
        </Card>

        {/* SEES Formula */}
        <Card className="p-6">
          <h2 className="font-display text-lg font-bold text-text-primary mb-2 flex items-center gap-2">
            <FlaskConical size={18} className="text-data-green" />
            SEES — Semantic Energy Efficiency Score
          </h2>
          <p className="text-sm text-text-muted mb-4">
            Measures the compute savings achieved by skipping full YOLO inference on background-only
            regions and propagating the priority map temporally instead.
          </p>
          <div className="rounded-btn p-4" style={{ background: 'rgba(15,20,38,0.8)', border: '1px solid rgba(0,255,135,0.2)' }}>
            <Formula latex={`\\text{SEES} = \\frac{T_{\\text{baseline}} - T_{\\text{semantic}}}{T_{\\text{baseline}}} \\times 100\\%`} />
          </div>
          <div className="mt-3 text-sm text-text-muted space-y-1">
            <p><em className="text-text-primary">T_baseline</em>: wall-clock time for full YOLO inference on every region of every frame,</p>
            <p><em className="text-text-primary">T_semantic</em>: wall-clock time with SemanticStream's temporal propagation (background regions skip inference),</p>
            <p>measured with <code className="font-mono text-xs text-accent-light">time.perf_counter()</code> per frame.</p>
          </div>
        </Card>

        {/* Architecture diagram */}
        <Card className="p-6">
          <h2 className="font-display text-lg font-bold text-text-primary mb-4">
            System Architecture (7 Layers)
          </h2>
          <ArchitectureDiagram />
        </Card>

        {/* 5-tier table */}
        <Card className="p-6">
          <h2 className="font-display text-lg font-bold text-text-primary mb-4">
            Semantic Priority Hierarchy
          </h2>
          <div className="overflow-x-auto">
            <table className="data-table w-full">
              <thead>
                <tr>
                  <th>Tier</th>
                  <th>Region Type</th>
                  <th>Weight (wᵢ)</th>
                  <th>QP (720p)</th>
                  <th>Trigger Condition</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {TIERS.map(({ tier, label, color, w, qp, trigger, desc }) => (
                  <tr key={tier}>
                    <td><TierBadge tier={tier} /></td>
                    <td className="text-text-primary font-medium">{label}</td>
                    <td><span className="font-mono text-sm" style={{ color }}>{w}</span></td>
                    <td><span className="font-mono text-sm" style={{ color }}>QP {qp}</span></td>
                    <td className="text-text-muted text-xs font-mono">{trigger}</td>
                    <td className="text-text-muted text-xs">{desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* References */}
        <Card className="p-6">
          <h2 className="font-display text-lg font-bold text-text-primary mb-4 flex items-center gap-2">
            <BookOpen size={18} className="text-text-muted" />
            References
          </h2>
          <div className="space-y-2">
            {REFERENCES.map((ref, i) => (
              <p key={i} className="text-xs text-text-muted leading-relaxed">
                {ref}
              </p>
            ))}
          </div>
        </Card>
      </div>
    </PageShell>
  )
}
