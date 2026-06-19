import { useMemo } from 'react'
import { HoverCard, HoverCardTrigger, HoverCardContent } from '@/components/ui/hover-card'
import { Badge } from '@/components/ui/badge'
import type { AgentVisibleResponse } from '@/types/contract'

// ── Constants ────────────────────────────────────────────────────────────────
const PALETTE = ['#6366f1', '#a855f7', '#06b6d4', '#22c55e', '#eab308', '#3b82f6']
const STATUS_COLOR: Record<string, string> = {
  published:  '#22c55e',
  superseded: '#64748b',
  draft:      '#eab308',
  failed:     '#ef4444',
}
const NW = 172, NH = 88, COL_GAP = 96, ROW_GAP = 22, PAD = 24

// ── Types ────────────────────────────────────────────────────────────────────
interface NodePos { x: number; y: number; cx: number; cy: number }

interface LayoutResult {
  nodes: AgentVisibleResponse[]
  positions: Record<string, NodePos>
  agentColor: Record<string, string>
  svgW: number
  svgH: number
}

// ── Layout algorithm: longest-path rank ──────────────────────────────────────
function computeLayout(responses: AgentVisibleResponse[], showInternal: boolean): LayoutResult {
  const nodes = responses.filter(r => {
    if (r.visibility === 'hidden') return false
    if (!showInternal && r.visibility === 'internal') return false
    return true
  })

  if (!nodes.length) return { nodes, positions: {}, agentColor: {}, svgW: 0, svgH: 0 }

  const idSet = new Set(nodes.map(r => r.response_id))
  const rankCache: Record<string, number> = {}

  function getrank(id: string): number {
    if (rankCache[id] !== undefined) return rankCache[id]
    const r = nodes.find(x => x.response_id === id)
    if (!r) return (rankCache[id] = 0)
    const deps = r.depends_on_response_ids.filter(d => idSet.has(d))
    if (!deps.length) return (rankCache[id] = 0)
    return (rankCache[id] = 1 + Math.max(...deps.map(getrank)))
  }
  nodes.forEach(r => getrank(r.response_id))

  const byRank: Record<number, AgentVisibleResponse[]> = {}
  nodes.forEach(r => {
    const rk = rankCache[r.response_id] ?? 0
    ;(byRank[rk] = byRank[rk] || []).push(r)
  })
  Object.values(byRank).forEach(col =>
    col.sort((a, b) => (a.publication_order ?? 0) - (b.publication_order ?? 0))
  )

  const maxCol  = Math.max(...Object.keys(byRank).map(Number))
  const maxRows = Math.max(...Object.values(byRank).map(c => c.length))
  const svgW    = PAD * 2 + (maxCol + 1) * NW + maxCol * COL_GAP
  const svgH    = PAD * 2 + maxRows * NH + (maxRows - 1) * ROW_GAP

  const positions: Record<string, NodePos> = {}
  Object.entries(byRank).forEach(([rank, col]) => {
    const colH   = col.length * NH + (col.length - 1) * ROW_GAP
    const startY = PAD + (svgH - PAD * 2 - colH) / 2
    col.forEach((r, i) => {
      const x = PAD + Number(rank) * (NW + COL_GAP)
      const y = startY + i * (NH + ROW_GAP)
      positions[r.response_id] = { x, y, cx: x + NW / 2, cy: y + NH / 2 }
    })
  })

  const agentNames = [...new Set(responses.map(r => r.agent_name))]
  const agentColor: Record<string, string> = {}
  agentNames.forEach((n, i) => { agentColor[n] = PALETTE[i % PALETTE.length] })

  return { nodes, positions, agentColor, svgW, svgH }
}

// ── Edge SVG path ─────────────────────────────────────────────────────────────
function EdgePath({
  src, tgt, color, markerId,
}: { src: NodePos; tgt: NodePos; color: string; markerId: string }) {
  const x1 = src.x + NW, y1 = src.cy
  const x2 = tgt.x,      y2 = tgt.cy
  const dx = (x2 - x1) * 0.55
  return (
    <path
      d={`M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`}
      stroke={color}
      strokeWidth="1.8"
      fill="none"
      opacity={0.65}
      markerEnd={`url(#${markerId})`}
    />
  )
}

// ── Node SVG group ────────────────────────────────────────────────────────────
function NodeGroup({ r, pos, color }: { r: AgentVisibleResponse; pos: NodePos; color: string }) {
  const isInternal   = r.visibility === 'internal'
  const isSuperseded = r.status === 'superseded'
  const sc           = STATUS_COLOR[r.status] ?? STATUS_COLOR.published
  const opacity      = isSuperseded ? 0.52 : 1
  const nodeBg       = isInternal ? '#1e1630' : '#1a1d2e'
  const trunc        = (s: string, n: number) => s.length > n ? s.slice(0, n) + '…' : s
  const init         = r.agent_name.charAt(0).toUpperCase()
  const nameText     = trunc(r.agent_name, 16)
  const roleText     = trunc(r.agent_role || '', 18)
  const preview      = trunc((r.content || '').replace(/\n[\s\S]*/m, '').trim(), 28)

  return (
    <g transform={`translate(${pos.x},${pos.y})`} opacity={opacity}>
      {/* shadow */}
      <rect x="2" y="3" width={NW} height={NH} rx="11" fill="#000" opacity={0.25} />
      {/* main box */}
      <rect
        width={NW} height={NH} rx="10"
        fill={nodeBg} stroke={color} strokeWidth="1.5"
        strokeDasharray={isInternal ? '5 3' : undefined}
      />
      {/* left accent */}
      <rect x="0" y="12" width="4" height={NH - 24} rx="2" fill={color} />
      {/* avatar circle */}
      <circle cx="24" cy="28" r="13" fill={color} opacity={0.9} />
      <text x="24" y="32.5" textAnchor="middle" fontSize="11" fontWeight="700" fontFamily="system-ui,sans-serif" fill="white">{init}</text>
      {/* name */}
      <text x="45" y="23" fontSize="11.5" fontWeight="700" fontFamily="system-ui,sans-serif" fill={color}>{nameText}</text>
      {/* role */}
      <text x="45" y="37" fontSize="9.5" fontFamily="system-ui,sans-serif" fill="#94a3b8" fontStyle="italic">{roleText}</text>
      {/* divider */}
      <line x1="10" y1="48" x2={NW - 10} y2="48" stroke="#ffffff14" strokeWidth="1" />
      {/* preview */}
      <text x="12" y="62" fontSize="9.5" fontFamily="system-ui,sans-serif" fill="#7c8db0">{preview}</text>
      {/* status dot + text */}
      <circle cx={NW - 36} cy="15" r="4" fill={sc} />
      <text x={NW - 29} y="19" fontSize="9" fontFamily="system-ui,sans-serif" fill={sc}>{r.status}</text>
      {/* order badge */}
      <rect x={NW - 22} y={NH - 20} width="18" height="14" rx="4" fill={color} opacity={0.18} />
      <text x={NW - 13} y={NH - 9} textAnchor="middle" fontSize="9" fontWeight="700" fontFamily="system-ui,sans-serif" fill={color}>#{r.publication_order}</text>
      {/* internal lock */}
      {isInternal && <text x={NW - 14} y="40" fontSize="11" fill="#a855f7" opacity={0.85}>🔒</text>}
      {/* superseded strikethrough */}
      {isSuperseded && (
        <line x1="45" y1="21" x2={45 + Math.min(nameText.length, 16) * 6.5} y2="21" stroke="#64748b" strokeWidth="1.5" />
      )}
    </g>
  )
}

// ── Main DagView component ────────────────────────────────────────────────────
interface DagViewProps {
  responses: AgentVisibleResponse[]
  showInternal: boolean
}

export function DagView({ responses, showInternal }: DagViewProps) {
  const { nodes, positions, agentColor, svgW, svgH } = useMemo(
    () => computeLayout(responses, showInternal),
    [responses, showInternal],
  )

  if (!nodes.length) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground gap-2">
        <span className="text-3xl opacity-40">🔀</span>
        <span className="text-sm">No nodes to display</span>
      </div>
    )
  }

  const agentNames = [...new Set(responses.map(r => r.agent_name))]

  return (
    <div className="overflow-auto">
      <div className="relative" style={{ width: svgW, height: svgH }}>

        {/* SVG layer: dot-grid + edges + nodes */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width={svgW}
          height={svgH}
          style={{ display: 'block', position: 'absolute', top: 0, left: 0 }}
        >
          <defs>
            {/* dot grid */}
            <pattern id="dag-dots" x="0" y="0" width="24" height="24" patternUnits="userSpaceOnUse">
              <circle cx="12" cy="12" r="0.8" fill="#ffffff0a" />
            </pattern>
            {/* arrowhead per agent */}
            {agentNames.map((name, i) => (
              <marker
                key={name}
                id={`arr-${i}`}
                viewBox="0 0 10 10"
                refX="9" refY="5"
                markerWidth="7" markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M0,1 L9,5 L0,9 Z" fill={agentColor[name]} opacity={0.85} />
              </marker>
            ))}
          </defs>

          {/* dot background */}
          <rect width={svgW} height={svgH} fill="url(#dag-dots)" />

          {/* edges */}
          {nodes.flatMap(r =>
            r.depends_on_response_ids
              .filter(depId => positions[depId] && positions[r.response_id])
              .map(depId => {
                const srcNode = nodes.find(n => n.response_id === depId)
                const color   = agentColor[srcNode?.agent_name ?? ''] ?? '#6366f1'
                const ai      = agentNames.indexOf(srcNode?.agent_name ?? '')
                return (
                  <EdgePath
                    key={`${depId}->${r.response_id}`}
                    src={positions[depId]}
                    tgt={positions[r.response_id]}
                    color={color}
                    markerId={`arr-${ai}`}
                  />
                )
              })
          )}

          {/* nodes */}
          {nodes.map(r =>
            positions[r.response_id] ? (
              <NodeGroup
                key={r.response_id}
                r={r}
                pos={positions[r.response_id]}
                color={agentColor[r.agent_name] ?? '#6366f1'}
              />
            ) : null
          )}
        </svg>

        {/* HoverCard trigger overlay — invisible divs positioned over each node */}
        {nodes.map(r => {
          const pos = positions[r.response_id]
          if (!pos) return null
          const statusVariant = r.status as 'published' | 'superseded' | 'draft' | 'failed'
          return (
            <HoverCard key={r.response_id} openDelay={200} closeDelay={100}>
              <HoverCardTrigger asChild>
                <div
                  className="absolute cursor-pointer rounded-xl"
                  style={{ left: pos.x, top: pos.y, width: NW, height: NH }}
                />
              </HoverCardTrigger>
              <HoverCardContent className="w-80">
                <div className="flex items-center gap-2 mb-2">
                  <div
                    className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
                    style={{ background: agentColor[r.agent_name] ?? '#6366f1' }}
                  >
                    {r.agent_name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="text-xs font-bold" style={{ color: agentColor[r.agent_name] ?? '#6366f1' }}>
                      {r.agent_name}
                    </div>
                    {r.agent_role && (
                      <div className="text-[10px] text-muted-foreground italic">{r.agent_role}</div>
                    )}
                  </div>
                  <div className="ml-auto flex gap-1">
                    <Badge variant={statusVariant}>{r.status}</Badge>
                    {r.visibility === 'internal' && <Badge variant="internal">internal</Badge>}
                  </div>
                </div>
                <p className="text-xs text-foreground leading-relaxed whitespace-pre-wrap max-h-40 overflow-y-auto">
                  {r.content}
                </p>
                {r.metadata && Object.keys(r.metadata).length > 0 && (
                  <div className="mt-2 pt-2 border-t border-border flex flex-wrap gap-1">
                    {Object.entries(r.metadata).map(([k, v]) => (
                      <span key={k} className="text-[10px] text-muted-foreground">
                        <span className="text-foreground/60">{k}:</span> {String(v)}
                      </span>
                    ))}
                  </div>
                )}
              </HoverCardContent>
            </HoverCard>
          )
        })}
      </div>
    </div>
  )
}
