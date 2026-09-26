import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useFormat } from '../lib/hooks'

export type SeriesDef = { key: string; label: string; color: string; unit: string; limit?: number }

export const CHART = {
  moisture: '#1f5a78',
  humidity: '#1f5a78',
  temperature: '#a9542a',
  band: '#2e7048',
  grid: '#e2d9c4',
  axis: '#5e6a5f',
}

/** Time series with an optional shaded target band (ideal range). Data only: no
 * decorative charts. `limit` draws a dashed safe-limit line for that series. */
export function TimeSeriesChart({
  data,
  series,
  height = 200,
  band,
  domain,
}: {
  data: Record<string, any>[]
  series: SeriesDef[]
  height?: number
  band?: { from: number; to: number; color?: string }
  domain?: [number, number]
}) {
  const f = useFormat()
  // Keep safe limits and target bands inside the view so the distance to them is visible.
  const marks = [...series.map((s) => s.limit), band?.from, band?.to].filter((v): v is number => v != null)
  const autoDomain: [(n: number) => number, (n: number) => number] = [
    (min) => Math.floor(Math.min(min, ...marks) - 2),
    (max) => Math.ceil(Math.max(max, ...marks) + 2),
  ]
  return (
    <div style={{ width: '100%', height }} className="num text-xs">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 6, right: 14, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="ts" tickFormatter={f.time} minTickGap={48} tick={{ fontSize: 11, fill: CHART.axis }} axisLine={{ stroke: CHART.grid }} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: CHART.axis }} domain={domain ?? autoDomain} axisLine={false} tickLine={false} width={34} tickFormatter={(v: number) => String(Math.round(v))} allowDecimals={false} />
          <Tooltip
            labelFormatter={(v) => f.dateTime(String(v))}
            formatter={(v, name) => [typeof v === 'number' ? v.toFixed(1) : String(v), name]}
            contentStyle={{ borderRadius: 8, borderColor: CHART.grid, fontSize: 12 }}
          />
          {band && <ReferenceArea y1={band.from} y2={band.to} fill={band.color ?? CHART.band} fillOpacity={0.08} stroke="none" />}
          {series.map((s) =>
            s.limit != null ? <ReferenceLine key={`${s.key}-limit`} y={s.limit} stroke={s.color} strokeDasharray="4 4" strokeOpacity={0.7} /> : null,
          )}
          {series.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={`${s.label} (${s.unit})`} stroke={s.color} dot={false} strokeWidth={2} isAnimationActive={false} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Legend rendered as HTML (clearer on phones than an in-chart legend). */
export function ChartLegend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4" style={{ background: i.dashed ? `repeating-linear-gradient(90deg, ${i.color} 0 4px, transparent 4px 7px)` : i.color }} />
          {i.label}
        </li>
      ))}
    </ul>
  )
}

/** [{ts, metric, value}] -> [{ts, metricA, metricB}] */
export function pivotReadings(rows: { ts: string; metric: string; value: number }[]) {
  const byTs = new Map<string, Record<string, any>>()
  for (const r of rows) {
    const row = byTs.get(r.ts) ?? { ts: r.ts }
    row[r.metric] = r.value
    byTs.set(r.ts, row)
  }
  return [...byTs.values()]
}
