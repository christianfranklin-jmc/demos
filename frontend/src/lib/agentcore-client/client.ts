/**
 * AgentCore SSE streaming client.
 *
 * Connects to the AgentCore Runtime endpoint and streams responses
 * as Server-Sent Events. Supports Cognito JWT auth when configured.
 *
 * Based on FAST template: frontend/src/lib/agentcore-client/client.ts
 */

export interface AgentCoreClientConfig {
  agentUrl: string
  getAccessToken?: () => Promise<string>
}

export interface StreamCallbacks {
  onToken: (token: string) => void
  onComplete: () => void
  onError: (error: Error) => void
}

export class AgentCoreClient {
  private config: AgentCoreClientConfig

  constructor(config: AgentCoreClientConfig) {
    this.config = config
  }

  async stream(prompt: string, callbacks: StreamCallbacks): Promise<void> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (this.config.getAccessToken) {
      const token = await this.config.getAccessToken()
      headers['Authorization'] = `Bearer ${token}`
    }

    try {
      const response = await fetch(`${this.config.agentUrl}/invocations`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ prompt }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('Response body is not readable')
      }

      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        callbacks.onToken(chunk)
      }

      callbacks.onComplete()
    } catch (error) {
      callbacks.onError(error instanceof Error ? error : new Error(String(error)))
    }
  }
}
