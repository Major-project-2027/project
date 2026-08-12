import { useQuery } from '@tanstack/react-query'
import { GraduationCap, Users, ServerCog, ShieldAlert } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { StatCard } from '@/components/dashboard/StatCard'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { EngagementTrendChart } from '@/components/charts/EngagementTrendChart'
import { reportsApi } from '@/services/api/endpoints'
import { Badge } from '@/components/ui/Badge'

const systemChecks = [
  { name: 'Face Authentication Service', status: 'operational', latency: '42ms' },
  { name: 'Emotion Detection Model', status: 'operational', latency: '58ms' },
  { name: 'Gaze & Head Pose Estimation', status: 'operational', latency: '61ms' },
  { name: 'Object Detection (YOLO)', status: 'degraded', latency: '210ms' },
  { name: 'LSTM Prediction Engine', status: 'operational', latency: '35ms' },
  { name: 'Voice Analysis Pipeline', status: 'operational', latency: '48ms' },
]

export function AdminDashboardPage() {
  const trendQuery = useQuery({ queryKey: ['engagement-trend'], queryFn: reportsApi.engagementTrend })

  return (
    <AppShell role="admin" title="Admin Overview">
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Teachers" value="48" icon={GraduationCap} tone="focus" />
          <StatCard label="Students" value="1,240" icon={Users} tone="engaged" />
          <StatCard label="Active sessions" value="6" icon={ServerCog} tone="attention" />
          <StatCard label="Critical alerts (24h)" value="14" icon={ShieldAlert} tone="critical" />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader className="pb-3">
              <CardTitle>Platform-wide engagement</CardTitle>
              <CardDescription>Aggregated across all departments, last 14 days</CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              <EngagementTrendChart data={trendQuery.data ?? []} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle>AI model health</CardTitle>
              <CardDescription>Inference pipeline status</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 pt-3">
              {systemChecks.map((s) => (
                <div key={s.name} className="flex items-center justify-between rounded-lg border border-border-light p-2.5 dark:border-border-dark">
                  <div>
                    <p className="text-sm font-medium text-text-light dark:text-text-dark">{s.name}</p>
                    <p className="font-mono text-[11px] text-textmuted-light dark:text-textmuted-dark">{s.latency} avg latency</p>
                  </div>
                  <Badge variant={s.status === 'operational' ? 'engaged' : 'attention'}>{s.status}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  )
}
