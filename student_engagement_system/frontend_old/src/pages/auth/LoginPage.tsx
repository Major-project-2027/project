import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Mail, Lock } from 'lucide-react'
import { AuthLayout } from './AuthLayout'
import { Input, Label } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { loginSchema, type LoginFormValues } from '@/features/auth/schemas'
import { authApi } from '@/services/api/endpoints'
import { useAppDispatch } from '@/hooks/useAppStore'
import { setCredentials } from '@/store/slices/authSlice'

export function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [serverError, setServerError] = useState('')
  const navigate = useNavigate()
  const dispatch = useAppDispatch()

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  const onSubmit = async (values: LoginFormValues) => {
    setServerError('')
    try {
      const { user, token } = await authApi.login(values.email, values.password)
      dispatch(setCredentials({ user, token }))
      navigate(user.role === 'teacher' ? '/teacher' : '/student')
    } catch {
      setServerError('We could not sign you in. Check your credentials and try again.')
    }
  }

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to your Cognivue classroom account.">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div>
          <Label htmlFor="email">Email</Label>
          <div className="relative">
            <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-textmuted-light dark:text-textmuted-dark" />
            <Input id="email" type="email" placeholder="you@bit.edu" className="pl-9" {...register('email')} error={errors.email?.message} />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link to="/forgot-password" className="text-xs font-medium text-focus-500 hover:underline">Forgot password?</Link>
          </div>
          <div className="relative">
            <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-textmuted-light dark:text-textmuted-dark" />
            <Input id="password" type={showPassword ? 'text' : 'password'} placeholder="••••••••" className="pl-9 pr-9" {...register('password')} error={errors.password?.message} />
            <button type="button" onClick={() => setShowPassword((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-textmuted-light dark:text-textmuted-dark">
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {serverError && <p className="rounded-lg bg-critical-500/10 px-3 py-2 text-sm text-critical-600 dark:text-critical-400">{serverError}</p>}

        <Button type="submit" className="w-full" loading={isSubmitting}>Sign in</Button>
      </form>

      <p className="mt-6 text-center text-sm text-textmuted-light dark:text-textmuted-dark">
        Don't have an account? <Link to="/register" className="font-medium text-focus-500 hover:underline">Create one</Link>
      </p>
      <p className="mt-3 text-center text-xs text-textmuted-light/70 dark:text-textmuted-dark/70">
        Demo: use any email containing "teacher" or "student"
      </p>
    </AuthLayout>
  )
}
