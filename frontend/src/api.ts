const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message) }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...options, credentials: 'include', cache: 'no-store', headers: { 'Content-Type': 'application/json', ...options.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map((item: { loc?: string[]; msg?: string }) => `${item.loc?.slice(1).join(' ') || 'Input'}: ${item.msg || 'Invalid value'}`).join('; ')
      : detail?.message || `Request failed (${response.status})`
    if (response.status === 401 && !path.startsWith('/api/auth/')) {
      window.dispatchEvent(new Event('fitpilot-session-expired'))
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T,>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
}
