import { useState } from 'react'
import { Link } from 'react-router-dom'
import { GraduationCap, Mail, MessageCircle, LifeBuoy } from 'lucide-react'
import { Input, Label } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'

export function SupportPage() {
  const [sent, setSent] = useState(false)

  return (
    <div className="min-h-screen bg-bg-light dark:bg-bg-dark">
      <header className="mx-auto flex max-w-4xl items-center gap-2 px-6 py-6">
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-focus-500 text-white"><GraduationCap className="h-4 w-4" /></div>
          <span className="font-display text-sm font-bold text-text-light dark:text-text-dark">Cognivue</span>
        </Link>
      </header>

      <div className="mx-auto max-w-4xl px-6 pb-20">
        <h1 className="font-display text-3xl font-bold text-text-light dark:text-text-dark">Support</h1>
        <p className="mt-2 text-textmuted-light dark:text-textmuted-dark">Reach our team for technical issues, account access, or platform feedback.</p>

        <div className="mt-8 grid gap-6 md:grid-cols-2">
          <Card>
            <CardContent className="space-y-4 pt-6">
              {sent ? (
                <div className="rounded-xl bg-engaged-500/10 p-5 text-center text-engaged-600 dark:text-engaged-400">
                  <MessageCircle className="mx-auto mb-2 h-6 w-6" />
                  Thanks — we've received your message and will respond within one business day.
                </div>
              ) : (
                <form onSubmit={(e) => { e.preventDefault(); setSent(true) }} className="space-y-4">
                  <div><Label>Subject</Label><Input placeholder="Camera not detected during class" required /></div>
                  <div><Label>Message</Label><textarea required rows={5} placeholder="Describe the issue..." className="w-full rounded-lg border border-border-light bg-transparent p-3 text-sm outline-none focus:border-focus-500 dark:border-border-dark" /></div>
                  <Button type="submit" className="w-full">Send message</Button>
                </form>
              )}
            </CardContent>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardContent className="flex items-start gap-3 pt-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-focus-500/10"><Mail className="h-5 w-5 text-focus-500" /></div>
                <div>
                  <p className="text-sm font-semibold text-text-light dark:text-text-dark">Email us</p>
                  <p className="text-sm text-textmuted-light dark:text-textmuted-dark">support@cognivue.app</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-start gap-3 pt-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-focus-500/10"><LifeBuoy className="h-5 w-5 text-focus-500" /></div>
                <div>
                  <p className="text-sm font-semibold text-text-light dark:text-text-dark">Response time</p>
                  <p className="text-sm text-textmuted-light dark:text-textmuted-dark">Within 1 business day for account issues; live-class technical issues are prioritized.</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
