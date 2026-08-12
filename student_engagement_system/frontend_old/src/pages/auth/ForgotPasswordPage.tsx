import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from 'react-router-dom'
import { MailCheck } from 'lucide-react'
import { AuthLayout } from './AuthLayout'
import { Input, Label } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { forgotPasswordSchema, type ForgotPasswordFormValues } from '@/features/auth/schemas'
import { authApi } from '@/services/api/endpoints'

export function ForgotPasswordPage() {
  const [sentTo, setSentTo] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: '' },
  })

  const onSubmit = async (values: ForgotPasswordFormValues) => {
    await authApi.forgotPassword(values.email)
    setSentTo(values.email)
  }

  return (
    <AuthLayout title="Reset your password" subtitle="We'll email you a link to get back into your account.">
      {sentTo ? (
        <div className="rounded-xl border border-border-light p-5 text-center dark:border-border-dark">
          <MailCheck className="mx-auto h-8 w-8 text-focus-500" />
          <p className="mt-3 text-sm font-medium text-text-light dark:text-text-dark">Check your inbox</p>
          <p className="mt-1 text-sm text-textmuted-light dark:text-textmuted-dark">We sent a reset link to {sentTo}.</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" placeholder="you@bit.edu" {...register('email')} error={errors.email?.message} />
          </div>
          <Button type="submit" className="w-full" loading={isSubmitting}>Send reset link</Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm text-textmuted-light dark:text-textmuted-dark">
        <Link to="/login" className="font-medium text-focus-500 hover:underline">Back to sign in</Link>
      </p>
    </AuthLayout>
  )
}
