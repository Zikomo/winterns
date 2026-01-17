import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { useAuth } from '@/hooks'
import { api } from '@/lib/api'
import { Card, Input, Button } from '@/components/ui'

interface RegisterFormData {
  email: string
  password: string
  confirmPassword: string
}

export function RegisterPage() {
  const { isAuthenticated, isLoading } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>()

  const password = watch('password')

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate('/dashboard', { replace: true })
    }
  }, [isAuthenticated, isLoading, navigate])

  const onSubmit = async (data: RegisterFormData) => {
    setError(null)
    try {
      await api.post('/auth/register', {
        email: data.email,
        password: data.password,
      })

      // Registration successful, redirect to login
      navigate('/login', {
        replace: true,
        state: { message: 'Account created successfully. Please sign in.' },
      })
    } catch (err) {
      if (err instanceof Error && 'response' in err) {
        const axiosError = err as { response?: { status: number; data?: { detail?: string } } }
        if (axiosError.response?.status === 400) {
          const detail = axiosError.response.data?.detail
          if (detail === 'REGISTER_USER_ALREADY_EXISTS') {
            setError('An account with this email already exists')
          } else {
            setError(detail || 'Invalid registration data')
          }
        } else {
          setError('An error occurred. Please try again.')
        }
      } else {
        setError('An error occurred. Please try again.')
      }
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 px-4">
      <Card className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Create an account
          </h1>
          <p className="text-gray-600">
            Get started with Wintern today
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              {...register('email', {
                required: 'Email is required',
                pattern: {
                  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                  message: 'Invalid email address',
                },
              })}
              error={errors.email?.message}
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Password
            </label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              {...register('password', {
                required: 'Password is required',
                minLength: {
                  value: 8,
                  message: 'Password must be at least 8 characters',
                },
              })}
              error={errors.password?.message}
            />
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
              Confirm Password
            </label>
            <Input
              id="confirmPassword"
              type="password"
              autoComplete="new-password"
              {...register('confirmPassword', {
                required: 'Please confirm your password',
                validate: (value) =>
                  value === password || 'Passwords do not match',
              })}
              error={errors.confirmPassword?.message}
            />
          </div>

          <Button
            type="submit"
            loading={isSubmitting}
            className="w-full"
          >
            Create account
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-600">
          Already have an account?{' '}
          <Link to="/login" className="text-blue-600 hover:text-blue-700 font-medium">
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  )
}
