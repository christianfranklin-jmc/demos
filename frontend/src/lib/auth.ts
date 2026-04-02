/**
 * Cognito PKCE Authentication
 *
 * Implements Authorization Code flow with PKCE for the Platform Agent.
 * Uses browser crypto API — no external dependencies.
 */

const COGNITO_DOMAIN = import.meta.env.VITE_COGNITO_DOMAIN || ''
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID || ''
const REDIRECT_URI =
  import.meta.env.VITE_COGNITO_REDIRECT_URI ||
  `${window.location.origin}/auth/callback`

const TOKEN_KEY = 'pa_access_token'
const ID_TOKEN_KEY = 'pa_id_token'
const REFRESH_KEY = 'pa_refresh_token'
const EXPIRY_KEY = 'pa_token_expiry'
const VERIFIER_KEY = 'pa_pkce_verifier'

/** Check if Cognito auth is configured */
export function isAuthEnabled(): boolean {
  return Boolean(COGNITO_DOMAIN && CLIENT_ID)
}

/** Generate PKCE code verifier + challenge */
async function generatePKCE(): Promise<{ verifier: string; challenge: string }> {
  const array = new Uint8Array(32)
  crypto.getRandomValues(array)
  const verifier = btoa(String.fromCharCode(...array))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '')

  const hash = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(verifier)
  )
  const challenge = btoa(String.fromCharCode(...new Uint8Array(hash)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '')

  return { verifier, challenge }
}

/** Redirect to Cognito hosted login */
export async function login(): Promise<void> {
  const { verifier, challenge } = await generatePKCE()
  sessionStorage.setItem(VERIFIER_KEY, verifier)

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    scope: 'email openid profile',
    code_challenge_method: 'S256',
    code_challenge: challenge,
  })

  window.location.href = `${COGNITO_DOMAIN}/oauth2/authorize?${params}`
}

/** Exchange auth code for tokens (called from callback route) */
export async function handleCallback(): Promise<boolean> {
  const params = new URLSearchParams(window.location.search)
  const code = params.get('code')
  const verifier = sessionStorage.getItem(VERIFIER_KEY)

  if (!code || !verifier) return false

  const response = await fetch(`${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: CLIENT_ID,
      redirect_uri: REDIRECT_URI,
      code,
      code_verifier: verifier,
    }),
  })

  if (!response.ok) return false

  const data = await response.json()
  localStorage.setItem(TOKEN_KEY, data.access_token)
  localStorage.setItem(ID_TOKEN_KEY, data.id_token)
  if (data.refresh_token) {
    localStorage.setItem(REFRESH_KEY, data.refresh_token)
  }
  localStorage.setItem(
    EXPIRY_KEY,
    String(Date.now() + data.expires_in * 1000)
  )
  sessionStorage.removeItem(VERIFIER_KEY)

  // Clean URL
  window.history.replaceState({}, '', '/')
  return true
}

/** Get current access token (null if not authenticated or expired) */
export function getAccessToken(): string | null {
  const token = localStorage.getItem(TOKEN_KEY)
  const expiry = localStorage.getItem(EXPIRY_KEY)

  if (!token || !expiry) return null
  if (Date.now() > Number(expiry) - 60_000) {
    // Token expired or expiring within 60s
    return null
  }
  return token
}

/**
 * Get ID token for AgentCore Runtime calls.
 *
 * Cognito access tokens don't include an `aud` claim, but
 * AgentCore's JWT authorizer validates `aud`. Cognito ID tokens
 * set `aud` = client_id, so we use the ID token for Runtime invocations.
 */
export function getIdToken(): string | null {
  const token = localStorage.getItem(ID_TOKEN_KEY)
  const expiry = localStorage.getItem(EXPIRY_KEY)

  if (!token || !expiry) return null
  if (Date.now() > Number(expiry) - 60_000) {
    return null
  }
  return token
}

/** Get user info from ID token */
export function getUserInfo(): { email: string; sub: string } | null {
  const idToken = localStorage.getItem(ID_TOKEN_KEY)
  if (!idToken) return null

  try {
    const payload = idToken.split('.')[1]
    const decoded = JSON.parse(atob(payload))
    return { email: decoded.email || '', sub: decoded.sub || '' }
  } catch {
    return null
  }
}

/** Clear tokens and redirect to Cognito logout */
export function logout(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(ID_TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem(EXPIRY_KEY)

  if (isAuthEnabled()) {
    const params = new URLSearchParams({
      client_id: CLIENT_ID,
      logout_uri: window.location.origin,
    })
    window.location.href = `${COGNITO_DOMAIN}/logout?${params}`
  }
}

/** Check if user is currently authenticated */
export function isAuthenticated(): boolean {
  return getAccessToken() !== null
}
