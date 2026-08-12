import { useParams } from 'react-router-dom'
import { Trophy, Download, Users } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Avatar } from '@/components/ui/Avatar'
import { ConfidenceRing } from '@/components/monitoring/ConfidenceRing'
import { STUDENT_NAMES } from '@/mocks/data'
import type { UserRole } from '@/types/domain'

export function ResultPage({ role }: { role: UserRole }) {
  const { testId } = useParams()

  if (role === 'student') {
    const score = 34
    const total = 40
    return (
      <AppShell role="student" title="Test Result">
        <div className="mx-auto max-w-xl">
          <Card>
            <CardContent className="flex flex-col items-center pt-8 text-center">
              <ConfidenceRing value={(score / total) * 100} size={100} strokeWidth={9} label="score" />
              <h2 className="mt-4 font-display text-xl font-bold text-text-light dark:text-text-dark">You scored {score} / {total}</h2>
              <p className="mt-1 text-sm text-textmuted-light dark:text-textmuted-dark">Computer Vision — Final Assessment · Test ID {testId}</p>
              <div className="mt-5 grid w-full grid-cols-3 gap-3 text-center">
                <div className="rounded-lg bg-black/[0.03] p-3 dark:bg-white/[0.04]"><p className="text-xs text-textmuted-light dark:text-textmuted-dark">Rank</p><p className="font-display font-bold text-text-light dark:text-text-dark">6 / 42</p></div>
                <div className="rounded-lg bg-black/[0.03] p-3 dark:bg-white/[0.04]"><p className="text-xs text-textmuted-light dark:text-textmuted-dark">Time taken</p><p className="font-display font-bold text-text-light dark:text-text-dark">38 min</p></div>
                <div className="rounded-lg bg-black/[0.03] p-3 dark:bg-white/[0.04]"><p className="text-xs text-textmuted-light dark:text-textmuted-dark">Integrity</p><p className="font-display font-bold text-engaged-600 dark:text-engaged-400">Clean</p></div>
              </div>
              <Button variant="outline" className="mt-6"><Download className="h-4 w-4" />Download certificate</Button>
            </CardContent>
          </Card>
        </div>
      </AppShell>
    )
  }

  const rows = STUDENT_NAMES.map((name, i) => ({
    name,
    score: Math.round(20 + Math.random() * 20),
    integrity: Math.random() > 0.85 ? 'flagged' : 'clean',
    time: `${30 + Math.floor(Math.random() * 15)} min`,
    id: `s-${2000 + i}`,
  })).sort((a, b) => b.score - a.score)

  return (
    <AppShell role="teacher" title="Test Results">
      <Card>
        <CardHeader className="flex-col items-stretch gap-3 sm:flex-row sm:items-center">
          <div>
            <CardTitle className="flex items-center gap-2"><Trophy className="h-4 w-4 text-focus-500" />Class results</CardTitle>
            <CardDescription>Test ID {testId} · <Users className="inline h-3.5 w-3.5" /> {rows.length} submissions</CardDescription>
          </div>
          <Button size="sm" variant="outline" className="sm:ml-auto"><Download className="h-4 w-4" />Export results</Button>
        </CardHeader>
        <CardContent className="pt-3">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-light text-xs text-textmuted-light dark:border-border-dark dark:text-textmuted-dark">
                <th className="pb-2 font-medium">Student</th>
                <th className="pb-2 font-medium">Score</th>
                <th className="pb-2 font-medium">Time</th>
                <th className="pb-2 font-medium">Integrity</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border-light last:border-0 dark:border-border-dark">
                  <td className="py-2.5"><div className="flex items-center gap-2"><Avatar name={r.name} size={26} /><span className="text-text-light dark:text-text-dark">{r.name}</span></div></td>
                  <td className="py-2.5 font-mono text-textmuted-light dark:text-textmuted-dark">{r.score} / 40</td>
                  <td className="py-2.5 text-textmuted-light dark:text-textmuted-dark">{r.time}</td>
                  <td className="py-2.5"><Badge variant={r.integrity === 'clean' ? 'engaged' : 'critical'}>{r.integrity}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </AppShell>
  )
}
