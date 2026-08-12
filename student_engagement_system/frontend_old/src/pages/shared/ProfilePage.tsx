import { Camera, ScanFace, Mail, Building2 } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Input, Label } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import { useAppSelector } from '@/hooks/useAppStore'
import type { UserRole } from '@/types/domain'
import { currentTeacher, currentStudent } from '@/mocks/data'

export function ProfilePage({ role }: { role: UserRole }) {
  const authUser = useAppSelector((s) => s.auth.user)
  const user = authUser ?? (role === 'teacher' ? currentTeacher : currentStudent)

  return (
    <AppShell role={role} title="Profile">
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1 h-fit">
          <CardContent className="flex flex-col items-center pt-6 text-center">
            <div className="relative">
              <Avatar name={user.name} size={88} />
              <button className="absolute bottom-0 right-0 flex h-7 w-7 items-center justify-center rounded-full bg-focus-500 text-white shadow">
                <Camera className="h-3.5 w-3.5" />
              </button>
            </div>
            <p className="mt-4 font-display text-lg font-semibold text-text-light dark:text-text-dark">{user.name}</p>
            <p className="text-sm text-textmuted-light dark:text-textmuted-dark capitalize">{user.role}</p>
            <div className="mt-3 flex gap-2">
              <Badge variant="focus">{role === 'teacher' ? `${currentTeacher.totalClasses} classes taught` : currentStudent.rollNumber}</Badge>
            </div>
            {role === 'student' && (
              <div className="mt-4 flex w-full items-center justify-between rounded-lg bg-engaged-500/10 px-3 py-2 text-sm text-engaged-600 dark:text-engaged-400">
                <span className="flex items-center gap-1.5"><ScanFace className="h-4 w-4" />Face enrolled</span>
                <Button size="sm" variant="ghost">Re-scan</Button>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="pb-3"><CardTitle>Personal information</CardTitle><CardDescription>Update your account details</CardDescription></CardHeader>
          <CardContent className="grid gap-4 pt-3 sm:grid-cols-2">
            <div>
              <Label>Full name</Label>
              <Input defaultValue={user.name} />
            </div>
            <div>
              <Label>Email</Label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-textmuted-light dark:text-textmuted-dark" />
                <Input defaultValue={user.email} className="pl-9" />
              </div>
            </div>
            <div>
              <Label>Department</Label>
              <div className="relative">
                <Building2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-textmuted-light dark:text-textmuted-dark" />
                <Input defaultValue={user.department ?? 'Computer Science & Engineering'} className="pl-9" />
              </div>
            </div>
            {role === 'student' && (
              <div>
                <Label>Roll number</Label>
                <Input defaultValue={currentStudent.rollNumber} disabled />
              </div>
            )}
            {role === 'teacher' && (
              <div>
                <Label>Subjects</Label>
                <Input defaultValue={currentTeacher.subjects.join(', ')} />
              </div>
            )}
            <div className="sm:col-span-2 flex justify-end gap-2">
              <Button variant="outline">Cancel</Button>
              <Button>Save changes</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
