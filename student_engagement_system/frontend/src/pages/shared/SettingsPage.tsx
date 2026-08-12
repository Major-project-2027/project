import { useState } from 'react'
import { Moon, Sun, Monitor } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Switch } from '@/components/ui/Switch'
import { Button } from '@/components/ui/Button'
import { useTheme } from '@/context/ThemeContext'
import { cn } from '@/lib/utils'
import type { UserRole } from '@/types/domain'

export function SettingsPage({ role }: { role: UserRole }) {
  const { theme, setTheme } = useTheme()
  const [prefs, setPrefs] = useState({
    aiAlerts: true,
    emailDigest: true,
    cameraReminders: true,
    soundAlerts: false,
    autoJoin: role === 'student',
  })

  const toggle = (key: keyof typeof prefs) => setPrefs((p) => ({ ...p, [key]: !p[key] }))

  return (
    <AppShell role={role} title="Settings">
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-3"><CardTitle>Appearance</CardTitle><CardDescription>Choose how Cognivue looks on this device</CardDescription></CardHeader>
          <CardContent className="pt-3">
            <div className="grid grid-cols-3 gap-3">
              {([
                { value: 'light', label: 'Light', icon: Sun },
                { value: 'dark', label: 'Dark', icon: Moon },
                { value: 'system', label: 'System', icon: Monitor },
              ] as const).map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => opt.value !== 'system' && setTheme(opt.value)}
                  className={cn(
                    'flex flex-col items-center gap-2 rounded-xl border p-4 text-sm font-medium transition-colors',
                    theme === opt.value ? 'border-focus-500 bg-focus-500/10 text-focus-600 dark:text-focus-400' : 'border-border-light text-textmuted-light dark:border-border-dark dark:text-textmuted-dark',
                  )}
                >
                  <opt.icon className="h-5 w-5" />
                  {opt.label}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3"><CardTitle>Notification preferences</CardTitle><CardDescription>Control what you're alerted about</CardDescription></CardHeader>
          <CardContent className="space-y-4 pt-3">
            {[
              { key: 'aiAlerts' as const, label: 'Real-time AI alerts', desc: 'Drowsiness, distraction, and phone detection notices' },
              { key: 'emailDigest' as const, label: 'Weekly email digest', desc: 'A summary of engagement and attendance' },
              { key: 'cameraReminders' as const, label: 'Camera-off reminders', desc: 'Nudge when camera is off during a live class' },
              { key: 'soundAlerts' as const, label: 'Sound on critical alerts', desc: 'Play a sound for phone/multi-person detection' },
            ].map((item) => (
              <div key={item.key} className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-light dark:text-text-dark">{item.label}</p>
                  <p className="text-xs text-textmuted-light dark:text-textmuted-dark">{item.desc}</p>
                </div>
                <Switch checked={prefs[item.key]} onChange={() => toggle(item.key)} />
              </div>
            ))}
          </CardContent>
        </Card>

        {role === 'student' && (
          <Card>
            <CardHeader className="pb-3"><CardTitle>Session behavior</CardTitle><CardDescription>Defaults applied when you join a class</CardDescription></CardHeader>
            <CardContent className="space-y-4 pt-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-light dark:text-text-dark">Auto-join with camera on</p>
                  <p className="text-xs text-textmuted-light dark:text-textmuted-dark">Applies only where your teacher allows camera choice</p>
                </div>
                <Switch checked={prefs.autoJoin} onChange={() => toggle('autoJoin')} />
              </div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader className="pb-3"><CardTitle>Account security</CardTitle></CardHeader>
          <CardContent className="space-y-3 pt-3">
            <Button variant="outline" className="w-full justify-start">Change password</Button>
            <Button variant="outline" className="w-full justify-start">Two-factor authentication</Button>
            <Button variant="danger" className="w-full justify-start">Deactivate account</Button>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
