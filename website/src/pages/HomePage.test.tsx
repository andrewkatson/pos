import { render, screen } from '@testing-library/react'
import HomePage from './HomePage'

test('renders Home View placeholder', () => {
  render(<HomePage />)
  expect(screen.getByRole('heading', { name: 'Home View' })).toBeInTheDocument()
})
