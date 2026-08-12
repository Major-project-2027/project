import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { Button } from '@/components/ui/Button'

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg-light px-6 text-center dark:bg-bg-dark">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-focus-500/10">
        <Compass className="h-7 w-7 text-focus-500" />
      </div>
      <h1 className="font-display text-2xl font-bold text-text-light dark:text-text-dark">Page not found</h1>
      <p className="max-w-sm text-sm text-textmuted-light dark:text-textmuted-dark">The page you're looking for doesn't exist or may have moved.</p>
      <Link to="/"><Button>Back to home</Button></Link>
    </div>
  )
}
