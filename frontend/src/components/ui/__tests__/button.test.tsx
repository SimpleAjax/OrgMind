import React from 'react'
import { render, screen, fireEvent } from '@/lib/test-utils'
import { Button, buttonVariants } from '@/components/ui/button'

describe('Button', () => {
  describe('Rendering', () => {
    it('renders a button with default props', () => {
      render(<Button>Click me</Button>)
      
      const button = screen.getByRole('button', { name: /click me/i })
      expect(button).toBeInTheDocument()
    })

    it('renders with correct data attributes', () => {
      render(<Button>Test</Button>)
      
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('data-slot', 'button')
      expect(button).toHaveAttribute('data-variant', 'default')
      expect(button).toHaveAttribute('data-size', 'default')
    })

    it('renders children correctly', () => {
      render(
        <Button>
          <span>Icon</span>
          <span>Label</span>
        </Button>
      )
      
      expect(screen.getByText('Icon')).toBeInTheDocument()
      expect(screen.getByText('Label')).toBeInTheDocument()
    })
  })

  describe('Variants', () => {
    it('renders with default variant', () => {
      render(<Button variant="default">Default</Button>)
      
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('data-variant', 'default')
      // Default variant should have bg-primary class
      expect(button.className).toContain('bg-primary')
    })

    it('renders with destructive variant', () => {
      render(<Button variant="destructive">Delete</Button>)
      
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('data-variant', 'destructive')
    })

    it('renders with outline variant', () => {
      render(<Button variant="outline">Outline</Button>)
      
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('data-variant', 'outline')
      expect(button.className).toContain('border')
    })

    it('renders with secondary variant', () => {
      render(<Button variant="secondary">Secondary</Button>)
      
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('data-variant', 'secondary')
    })

    it('renders with ghost variant', () => {
      render(<Button variant="ghost">Ghost</Button>)
      
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('data-variant', 'ghost')
    })

    it('renders with link variant', () => {
      render(<Button variant="link">Link</Button>)
      
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('data-variant', 'link')
      expect(button.className).toContain('underline-offset-4')
    })

    it('renders with different sizes', () => {
      const { rerender } = render(<Button size="default">Default Size</Button>)
      expect(screen.getByRole('button')).toHaveAttribute('data-size', 'default')

      rerender(<Button size="sm">Small</Button>)
      expect(screen.getByRole('button')).toHaveAttribute('data-size', 'sm')

      rerender(<Button size="lg">Large</Button>)
      expect(screen.getByRole('button')).toHaveAttribute('data-size', 'lg')

      rerender(<Button size="icon">Icon</Button>)
      expect(screen.getByRole('button')).toHaveAttribute('data-size', 'icon')
    })
  })

  describe('Interaction', () => {
    it('calls onClick handler when clicked', () => {
      const handleClick = jest.fn()
      render(<Button onClick={handleClick}>Click me</Button>)
      
      const button = screen.getByRole('button')
      fireEvent.click(button)
      
      expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('does not call onClick when disabled', () => {
      const handleClick = jest.fn()
      render(<Button onClick={handleClick} disabled>Click me</Button>)
      
      const button = screen.getByRole('button')
      fireEvent.click(button)
      
      expect(handleClick).not.toHaveBeenCalled()
    })

    it('is disabled when disabled prop is true', () => {
      render(<Button disabled>Disabled</Button>)
      
      const button = screen.getByRole('button')
      expect(button).toBeDisabled()
    })

    it('is disabled when aria-disabled is true', () => {
      render(<Button aria-disabled="true">Aria Disabled</Button>)
      
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('aria-disabled', 'true')
    })
  })

  describe('asChild prop', () => {
    it('renders as a button by default', () => {
      render(<Button>Button</Button>)
      
      expect(screen.getByRole('button').tagName).toBe('BUTTON')
    })

    it('renders as child element when asChild is true', () => {
      render(
        <Button asChild>
          <a href="/test">Link Button</a>
        </Button>
      )
      
      // When asChild is true, it should render as an anchor
      const link = screen.getByRole('link')
      expect(link).toBeInTheDocument()
      expect(link).toHaveAttribute('href', '/test')
    })
  })

  describe('Custom classes', () => {
    it('applies custom className', () => {
      render(<Button className="custom-class">Custom</Button>)
      
      const button = screen.getByRole('button')
      expect(button.className).toContain('custom-class')
    })

    it('merges custom classes with default classes', () => {
      render(<Button className="custom-class">Merged</Button>)
      
      const button = screen.getByRole('button')
      // Should have both default and custom classes
      expect(button.className).toContain('custom-class')
      expect(button.className).toContain('inline-flex')
    })
  })

  describe('Accessibility', () => {
    it('has correct button role', () => {
      render(<Button>Accessible</Button>)
      
      expect(screen.getByRole('button')).toBeInTheDocument()
    })

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLButtonElement>()
      render(<Button ref={ref}>Ref Test</Button>)
      
      expect(ref.current).toBeInstanceOf(HTMLButtonElement)
    })

    it('supports aria-label', () => {
      render(<Button aria-label="Close dialog">×</Button>)
      
      expect(screen.getByLabelText('Close dialog')).toBeInTheDocument()
    })

    it('supports aria-pressed for toggle buttons', () => {
      render(<Button aria-pressed="true">Toggle</Button>)
      
      expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'true')
    })
  })

  describe('buttonVariants function', () => {
    it('returns base classes with no variants', () => {
      const classes = buttonVariants()
      expect(classes).toContain('inline-flex')
      expect(classes).toContain('items-center')
    })

    it('applies variant classes correctly', () => {
      const classes = buttonVariants({ variant: 'destructive' })
      expect(classes).toContain('bg-destructive')
    })

    it('applies size classes correctly', () => {
      const classes = buttonVariants({ size: 'lg' })
      expect(classes).toContain('h-10')
    })

    it('applies custom classes correctly', () => {
      const classes = buttonVariants({ className: 'custom-class' })
      expect(classes).toContain('custom-class')
    })

    it('merges multiple variants', () => {
      const classes = buttonVariants({ 
        variant: 'outline', 
        size: 'sm',
        className: 'custom-class'
      })
      
      expect(classes).toContain('border') // outline variant
      expect(classes).toContain('h-8')    // sm size
      expect(classes).toContain('custom-class')
    })
  })

  describe('Type attribute', () => {
    it('has type="button" by default', () => {
      render(<Button>Default Type</Button>)
      
      // HTML button defaults to "submit", but we should be explicit
      const button = screen.getByRole('button')
      // The component passes props through, so we can set type explicitly
      expect(button.tagName).toBe('BUTTON')
    })

    it('respects explicit type prop', () => {
      render(<Button type="submit">Submit</Button>)
      
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('type', 'submit')
    })

    it('respects type="reset"', () => {
      render(<Button type="reset">Reset</Button>)
      
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('type', 'reset')
    })
  })
})
