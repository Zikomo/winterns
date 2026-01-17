import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export interface RadioOption {
  value: string
  label: string
  description?: string
  disabled?: boolean
}

export interface RadioGroupProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
  options: RadioOption[]
  error?: string
}

export const RadioGroup = forwardRef<HTMLInputElement, RadioGroupProps>(
  ({ className, label, options, error, name, ...props }, ref) => {
    return (
      <fieldset className={cn('w-full', className)}>
        {label && (
          <legend className="mb-3 text-sm font-medium text-gray-700">
            {label}
          </legend>
        )}
        <div className="space-y-3">
          {options.map((option, index) => {
            const optionId = `${name}-${option.value}`
            return (
              <div key={option.value} className="flex items-start">
                <div className="flex h-5 items-center">
                  <input
                    ref={index === 0 ? ref : undefined}
                    type="radio"
                    id={optionId}
                    name={name}
                    value={option.value}
                    disabled={option.disabled}
                    className={cn(
                      'h-4 w-4 border-gray-300 text-blue-600',
                      'focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
                      'disabled:cursor-not-allowed disabled:opacity-50'
                    )}
                    {...props}
                  />
                </div>
                <div className="ml-3">
                  <label
                    htmlFor={optionId}
                    className={cn(
                      'text-sm font-medium',
                      option.disabled ? 'text-gray-400' : 'text-gray-700'
                    )}
                  >
                    {option.label}
                  </label>
                  {option.description && (
                    <p className="text-sm text-gray-500">{option.description}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </fieldset>
    )
  }
)

RadioGroup.displayName = 'RadioGroup'
