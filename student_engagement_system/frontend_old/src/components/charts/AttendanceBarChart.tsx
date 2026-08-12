import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import type { EngagementTrendPoint } from '@/types/domain'
import { useTheme } from '@/context/ThemeContext'

export function AttendanceBarChart({ data }: { data: EngagementTrendPoint[] }) {
  const { theme } = useTheme()
  const gridColor = theme === 'dark' ? '#242a3d' : '#e4e7ef'
  const textColor = theme === 'dark' ? '#8b91ab' : '#5b6274'

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 10, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid stroke={gridColor} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" tick={{ fill: textColor, fontSize: 11 }} axisLine={{ stroke: gridColor }} tickLine={false} />
        <YAxis tick={{ fill: textColor, fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 100]} />
        <Tooltip contentStyle={{ background: theme === 'dark' ? '#141826' : '#fff', border: `1px solid ${gridColor}`, borderRadius: 10, fontSize: 12 }} />
        <Bar dataKey="attendanceRate" name="Attendance %" fill="#22C55E" radius={[6, 6, 0, 0]} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer>
  )
}
