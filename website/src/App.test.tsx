import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

test('renders landing page', () => {
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  )
  expect(screen.getByText('Positive Only Social')).toBeInTheDocument()
})
