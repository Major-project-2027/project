import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
  role: z.enum(['teacher', 'student']),
})
export type LoginFormValues = z.infer<typeof loginSchema>

export const registerSchema = z
  .object({
    name: z.string().min(2, 'Enter your full name'),
    email: z.string().email('Enter a valid email address'),
    role: z.enum(['teacher', 'student']),
    password: z.string().min(6, 'Password must be at least 6 characters'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })
export type RegisterFormValues = z.infer<typeof registerSchema>

export const forgotPasswordSchema = z.object({
  email: z.string().email('Enter a valid email address'),
})
export type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>
