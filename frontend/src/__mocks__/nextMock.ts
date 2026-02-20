import React from 'react'

// ============================================================================
// Next.js Router Mock
// ============================================================================

export const useRouter = jest.fn(() => ({
  push: jest.fn(),
  replace: jest.fn(),
  refresh: jest.fn(),
  back: jest.fn(),
  forward: jest.fn(),
  prefetch: jest.fn(),
  pathname: '/',
  query: {},
  asPath: '/',
  events: {
    on: jest.fn(),
    off: jest.fn(),
    emit: jest.fn(),
  },
}))

export const usePathname = jest.fn(() => '/')
export const useSearchParams = jest.fn(() => new URLSearchParams())
export const useParams = jest.fn(() => ({}))

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter,
  usePathname,
  useSearchParams,
  useParams,
  redirect: jest.fn(),
  permanentRedirect: jest.fn(),
  notFound: jest.fn(),
}))

// ============================================================================
// Next.js Image Mock
// ============================================================================

export const Image = React.forwardRef<
  HTMLImageElement,
  React.ImgHTMLAttributes<HTMLImageElement> & {
    src: string
    alt: string
    width?: number | string
    height?: number | string
    fill?: boolean
    priority?: boolean
    loading?: 'eager' | 'lazy'
    placeholder?: 'blur' | 'empty'
    blurDataURL?: string
    unoptimized?: boolean
    onLoad?: React.ReactEventHandler<HTMLImageElement>
    onError?: React.ReactEventHandler<HTMLImageElement>
  }
>(({ src, alt, fill, priority, placeholder, blurDataURL, unoptimized, ...props }, ref) => {
  return React.createElement('img', {
    src,
    alt,
    ref,
    ...props,
    'data-fill': fill,
    'data-priority': priority,
    'data-placeholder': placeholder,
    'data-blurdataurl': blurDataURL,
    'data-unoptimized': unoptimized,
  })
})

Image.displayName = 'NextImage'

jest.mock('next/image', () => ({
  __esModule: true,
  default: Image,
}))

// ============================================================================
// Next.js Link Mock
// ============================================================================

export const Link = React.forwardRef<
  HTMLAnchorElement,
  React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string
    prefetch?: boolean
    replace?: boolean
    scroll?: boolean
    shallow?: boolean
    passHref?: boolean
  }
>(({ href, prefetch, replace, scroll, shallow, passHref, ...props }, ref) => {
  return React.createElement('a', {
    href,
    ref,
    ...props,
    'data-prefetch': prefetch,
    'data-replace': replace,
    'data-scroll': scroll,
    'data-shallow': shallow,
    'data-passhref': passHref,
  })
})

Link.displayName = 'NextLink'

jest.mock('next/link', () => ({
  __esModule: true,
  default: Link,
}))

// ============================================================================
// Next.js Head Mock
// ============================================================================

export const Head = ({ children }: { children?: React.ReactNode }) => {
  return React.createElement('div', { 'data-testid': 'next-head' }, children)
}

jest.mock('next/head', () => ({
  __esModule: true,
  default: Head,
}))

// ============================================================================
// Next.js Script Mock
// ============================================================================

export const Script = React.forwardRef<
  HTMLScriptElement,
  React.ScriptHTMLAttributes<HTMLScriptElement> & {
    strategy?: 'beforeInteractive' | 'afterInteractive' | 'lazyOnload' | 'worker'
  }
>(({ strategy, ...props }, ref) => {
  return React.createElement('script', {
    ...props,
    ref,
    'data-strategy': strategy,
  })
})

Script.displayName = 'NextScript'

jest.mock('next/script', () => ({
  __esModule: true,
  default: Script,
}))

// ============================================================================
// Helper Functions for Testing
// ============================================================================

/**
 * Reset all Next.js mocks to their initial state
 * Call this in beforeEach to ensure clean state between tests
 */
export function resetNextMocks() {
  const mockRouter = {
    push: jest.fn(),
    replace: jest.fn(),
    refresh: jest.fn(),
    back: jest.fn(),
    forward: jest.fn(),
    prefetch: jest.fn(),
    pathname: '/',
    query: {},
    asPath: '/',
    events: {
      on: jest.fn(),
      off: jest.fn(),
      emit: jest.fn(),
    },
  }

  useRouter.mockReturnValue(mockRouter)
  usePathname.mockReturnValue('/')
  useSearchParams.mockReturnValue(new URLSearchParams())
  useParams.mockReturnValue({})

  return { mockRouter }
}

/**
 * Setup router mock with custom pathname and query
 */
export function setupRouterMock(pathname: string, query: Record<string, string> = {}) {
  const urlSearchParams = new URLSearchParams(query)
  
  usePathname.mockReturnValue(pathname)
  useSearchParams.mockReturnValue(urlSearchParams)
  useParams.mockReturnValue(query)

  return { pathname, query, searchParams: urlSearchParams }
}

/**
 * Get the last call to router.push for assertion
 */
export function getRouterPushCalls() {
  const router = useRouter()
  return (router.push as jest.Mock).mock.calls
}

/**
 * Get the last call to router.replace for assertion
 */
export function getRouterReplaceCalls() {
  const router = useRouter()
  return (router.replace as jest.Mock).mock.calls
}
