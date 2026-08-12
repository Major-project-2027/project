import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import type { EngagementTrendPoint } from '@/types/domain'
import { useTheme } from '@/context/ThemeContext'

export function EngagementTrendChart({ data }: { data: EngagementTrendPoint[] }) {
  const { theme } = useTheme()
  const gridColor = theme === 'dark' ? '#242a3d' : '#e4e7ef'
  const textColor = theme === 'dark' ? '#8b91ab' : '#5b6274'

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ top: 10, right: 8, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="engagementFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4F5DFF" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#4F5DFF" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={gridColor} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" tick={{ fill: textColor, fontSize: 11 }} axisLine={{ stroke: gridColor }} tickLine={false} />
        <YAxis tick={{ fill: textColor, fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 100]} />
        <Tooltip
          contentStyle={{ background: theme === 'dark' ? '#141826' : '#fff', border: `1px solid ${gridColor}`, borderRadius: 10, fontSize: 12 }}
          labelStyle={{ color: textColor }}
        />
        <Area type="monotone" dataKey="avgEngagement" name="Avg. engagement" stroke="#4F5DFF" strokeWidth={2} fill="url(#engagementFill)" />
      </AreaChart>
    </ResponsiveContainer>
  )
}
