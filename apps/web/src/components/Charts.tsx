import { CartesianGrid, Legend, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useFormat } from '../lib/hooks'

export type SeriesDef = { key: string; label: string; color: string; unit: string; limit?: number }

/** `band` shades a target range (e.g. ideal soil moisture) behind the lines. */
export function TimeSeriesChart({
  data,
  series,
  height = 220,
  band,
}: {
  data: Record<string, any>[]
  series: SeriesDef[]
  height?: number
  band?: { from: number; to: number; color: string }
}) {
  const f = useFormat()
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid stroke="#e7e5e4" strokeDasharray="3 3" />
          <XAxis dataKey="ts" tickFormatter={f.time} minTickGap={40} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
          <Tooltip labelFormatter={(v) => f.dateTime(String(v))} formatter={(v, name) => [`${v}`, name]} />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
          {band && <ReferenceArea y1={band.from} y2={band.to} fill={band.color} fillOpacity={0.12} stroke="none" />}
          {series.map((s) =>
            s.limit != null ? <ReferenceLine key={`${s.key}-limit`} y={s.limit} stroke={s.color} strokeDasharray="4 4" strokeOpacity={0.6} /> : null,
          )}
          {series.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={`${s.label} (${s.unit})`} stroke={s.color} dot={false} strokeWidth={2} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
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
