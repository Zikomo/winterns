const TOKEN_KEY = 'token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

/**
 * Decode a base64url string (used in JWTs) to a UTF-8 string.
 * Base64url uses '-' and '_' instead of '+' and '/', and omits padding.
 * Properly handles UTF-8 encoded claims (e.g., non-ASCII names).
 */
function base64UrlDecode(str: string): string {
  // Replace base64url characters with base64 equivalents
  let base64 = str.replace(/-/g, '+').replace(/_/g, '/')
  // Add padding if needed
  const padding = base64.length % 4
  if (padding) {
    base64 += '='.repeat(4 - padding)
  }
  // Decode base64 to binary string, then convert to UTF-8
  const binaryStr = atob(base64)
  const bytes = Uint8Array.from(binaryStr, (c) => c.charCodeAt(0))
  return new TextDecoder().decode(bytes)
}

export function isAuthenticated(): boolean {
  const token = getToken()
  if (!token) return false

  // Check if token is expired by decoding JWT payload
  try {
    const parts = token.split('.')
    const payloadPart = parts[1]
    if (parts.length !== 3 || !payloadPart) return false
    const payload = JSON.parse(base64UrlDecode(payloadPart))
    const exp = payload.exp
    if (!exp) return true
    return Date.now() < exp * 1000
  } catch {
    // If we can't decode, assume invalid
    return false
  }
}

export function getGoogleAuthUrl(): string {
  const apiUrl = import.meta.env.VITE_API_URL || ''
  return `${apiUrl}/api/v1/auth/google/authorize`
}
