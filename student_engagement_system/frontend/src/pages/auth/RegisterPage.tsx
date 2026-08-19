import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from 'react-router-dom'
import { GraduationCap, User2 } from 'lucide-react'
import { AuthLayout } from './AuthLayout'
import { Input, Label } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import { registerSchema, type RegisterFormValues } from '@/features/auth/schemas'
import { authApi } from '@/services/api/endpoints'

export function RegisterPage() {
  const navigate = useNavigate()
  const [success, setSuccess] = useState(false)
  const { register, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { name: '', email: '', role: 'student', password: '', confirmPassword: '' },
  })
  const role = watch('role')

  const onSubmit = async (values: RegisterFormValues) => {
    await authApi.register(values)
    setSuccess(true)

    if (values.role === 'student') {
      // Face registration (capturing the student's registered face for
      // later live-class verification) needs an authenticated request,
      // and /register itself doesn't return a token -- so log in with the
      // credentials just submitted before handing off to that step,
      // rather than sending the student to a face-capture page with no
      // session and no way to save anything.
      try {
        await authApi.login(values.email, values.password, 'student')
        setTimeout(() => navigate('/register/face'), 1000)
        return
      } catch {
        // Fall through to the normal "redirect to sign in" path -- the
        // account was created successfully either way.
      }
    }

    setTimeout(() => navigate('/login'), 1400)
  }

  return (
    <AuthLayout title="Create your account" subtitle="Set up access to your classroom in under a minute.">
      {success ? (
        <div className="rounded-xl bg-engaged-500/10 px-4 py-3 text-sm text-engaged-600 dark:text-engaged-400">
          Account created. Redirecting you to sign in…
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <Label>I am a</Label>
            <div className="grid grid-cols-2 gap-3">
              {(['student', 'teacher'] as const).map((r) => (
                <button
                  type="button"
                  key={r}
                  onClick={() => setValue('role', r)}
                  className={cn(
                    'flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium capitalize transition-colors',
                    role === r
                      ? 'border-focus-500 bg-focus-500/10 text-focus-600 dark:text-focus-400'
                      : 'border-border-light text-textmuted-light dark:border-border-dark dark:text-textmuted-dark',
                  )}
                >
                  {r === 'teacher' ? <GraduationCap className="h-4 w-4" /> : <User2 className="h-4 w-4" />}
                  {r}
                </button>
              ))}
            </div>
          </div>

          <div>
            <Label htmlFor="name">Full name</Label>
            <Input id="name" placeholder="Aarav Mehta" {...register('name')} error={errors.name?.message} />
          </div>
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" placeholder="you@bit.edu" {...register('email')} error={errors.email?.message} />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" placeholder="••••••••" {...register('password')} error={errors.password?.message} />
          </div>
          <div>
            <Label htmlFor="confirmPassword">Confirm password</Label>
            <Input id="confirmPassword" type="password" placeholder="••••••••" {...register('confirmPassword')} error={errors.confirmPassword?.message} />
          </div>

          <Button type="submit" className="w-full" loading={isSubmitting}>Create account</Button>
        </form>
      )}

      <p className="mt-6 text-center text-sm text-textmuted-light dark:text-textmuted-dark">
        Already have an account? <Link to="/login" className="font-medium text-focus-500 hover:underline">Sign in</Link>
      </p>
    </AuthLayout>
  )
}
