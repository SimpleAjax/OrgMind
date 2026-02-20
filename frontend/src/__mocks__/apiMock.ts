// ============================================================================
// API Response Mocks
// ============================================================================

/**
 * Standard API response structure
 */
export interface ApiResponse<T = unknown> {
  data?: T
  error?: string
  message?: string
  status: number
  success: boolean
}

/**
 * Mock successful API response
 */
export function mockApiResponse<T>(data: T, message = 'Success'): ApiResponse<T> {
  return {
    data,
    message,
    status: 200,
    success: true,
  }
}

/**
 * Mock error API response
 */
export function mockApiErrorResponse(error: string, status = 400): ApiResponse {
  return {
    error,
    status,
    success: false,
  }
}

// ============================================================================
// Fetch Mock
// ============================================================================

/**
 * Create a mock fetch response
 */
export function createFetchResponse<T>(data: T, status = 200, statusText = 'OK'): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    json: jest.fn().mockResolvedValue(data),
    text: jest.fn().mockResolvedValue(JSON.stringify(data)),
    blob: jest.fn(),
    arrayBuffer: jest.fn(),
    formData: jest.fn(),
    clone: jest.fn(),
    body: null,
    bodyUsed: false,
    headers: new Headers(),
    redirect: jest.fn(),
    trailer: Promise.resolve(new Headers()),
    type: 'basic',
    url: '',
  } as unknown as Response
}

/**
 * Mock fetch implementation
 */
export const mockFetch = jest.fn<Promise<Response>, [RequestInfo | URL, RequestInit?]>()

/**
 * Setup fetch mock with predefined responses
 * 
 * Usage:
 * ```ts
 * setupFetchMock({
 *   'https://api.example.com/users': { id: 1, name: 'John' },
 *   'https://api.example.com/posts': [{ id: 1, title: 'Hello' }],
 * })
 * ```
 */
export function setupFetchMock(
  responses: Record<string, unknown>,
  defaultResponse: unknown = { error: 'Not found' },
  defaultStatus = 404
) {
  mockFetch.mockImplementation(async (url) => {
    const urlString = url.toString()
    
    // Find matching URL pattern
    for (const [pattern, data] of Object.entries(responses)) {
      if (urlString.includes(pattern) || urlString === pattern) {
        return createFetchResponse(data, 200)
      }
    }
    
    return createFetchResponse(defaultResponse, defaultStatus)
  })

  global.fetch = mockFetch
  return mockFetch
}

/**
 * Setup fetch mock with sequential responses (for testing loading states, retries, etc.)
 * 
 * Usage:
 * ```ts
 * setupSequentialFetch([
 *   { data: null, status: 500, statusText: 'Server Error' },
 *   { data: { id: 1 }, status: 200 },
 * ])
 * ```
 */
export function setupSequentialFetch(
  responses: Array<{ data: unknown; status?: number; statusText?: string }>
) {
  let callIndex = 0
  
  mockFetch.mockImplementation(async () => {
    const response = responses[callIndex] || responses[responses.length - 1]
    callIndex++
    
    return createFetchResponse(
      response.data,
      response.status ?? 200,
      response.statusText ?? 'OK'
    )
  })

  global.fetch = mockFetch
  return mockFetch
}

/**
 * Reset fetch mock
 */
export function resetFetchMock() {
  mockFetch.mockClear()
}

// ============================================================================
// Common API Response Mocks
// ============================================================================

export const commonApiResponses = {
  // User related
  user: {
    id: '1',
    email: 'user@example.com',
    name: 'John Doe',
    avatar: 'https://example.com/avatar.jpg',
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  
  // Auth related
  session: {
    user: {
      id: '1',
      email: 'user@example.com',
      name: 'John Doe',
    },
    expires: '2024-12-31T00:00:00Z',
  },
  
  // List responses
  users: [
    { id: '1', email: 'user1@example.com', name: 'User One' },
    { id: '2', email: 'user2@example.com', name: 'User Two' },
  ],
  
  // Error responses
  validationError: {
    error: 'Validation failed',
    details: [
      { field: 'email', message: 'Invalid email format' },
    ],
  },
  
  unauthorizedError: {
    error: 'Unauthorized',
    message: 'Please sign in to continue',
  },
  
  notFoundError: {
    error: 'Not found',
    message: 'The requested resource was not found',
  },
}

// ============================================================================
// Mock API Client (for use with libraries like SWR or React Query)
// ============================================================================

/**
 * Create a mock API client for testing hooks
 */
export function createMockApiClient<T>(response: T, delay = 0) {
  return jest.fn().mockImplementation(() => {
    return new Promise<T>((resolve) => {
      setTimeout(() => resolve(response), delay)
    })
  })
}

/**
 * Create a mock API client that fails
 */
export function createMockApiClientError(error: Error, delay = 0) {
  return jest.fn().mockImplementation(() => {
    return new Promise<never>((_, reject) => {
      setTimeout(() => reject(error), delay)
    })
  })
}
