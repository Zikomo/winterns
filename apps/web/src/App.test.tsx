import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

function renderWithProviders(ui: React.ReactElement, { route = '/' } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('App', () => {
  it('renders home page by default', () => {
    renderWithProviders(<App />)
    expect(screen.getByText('Wintern')).toBeInTheDocument()
  })

  it('renders health page when navigating to /health', () => {
    renderWithProviders(<App />, { route: '/health' })
    expect(screen.getByText('System Health Check')).toBeInTheDocument()
  })
})
