import { useState, useRef, useEffect, useCallback } from 'react'
import { AgentCoreClient, type StreamEvent, type AgentPattern } from './lib/agentcore-client'
import {
  isAuthEnabled,
  isAuthenticated,
  getAccessToken,
  getUserInfo,
  login,
  logout,
  handleCallback,
} from './lib/auth'

interface Message {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCall[]
}

interface ToolCall {
  id: string
  name: string
  input: string
  result?: string
}

// --- Backend mode detection ---

const runtimeArn = import.meta.env.VITE_AGENTCORE_RUNTIME_ARN || ''
const region = import.meta.env.VITE_AGENTCORE_REGION || 'us-east-1'
const pattern = (import.meta.env.VITE_AGENTCORE_PATTERN || 'strands-single-agent') as AgentPattern
const agentUrl = import.meta.env.VITE_AGENT_URL || 'http://localhost:8080'
const isAgentCore = Boolean(runtimeArn)

// AgentCore client (used when runtime ARN is configured)
const agentCoreClient = isAgentCore
  ? new AgentCoreClient({ runtimeArn, region, pattern })
  : null

/**
 * Platform Agent — Talk To Your Data
 *
 * Chat interface with phData dark branding. Supports two modes:
 * - Local: direct fetch to agent on localhost:8080
 * - AgentCore: SSE streaming via AgentCoreClient with JWT auth
 */
export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [authed, setAuthed] = useState(isAuthenticated())
  const [sessionId] = useState(() =>
    agentCoreClient?.generateSessionId() ?? crypto.randomUUID()
  )
  const [dbConfig, setDbConfig] = useState({
    host: '',
    port: '5432',
    database: '',
    user: '',
    password: '',
    driverType: 'postgresql',
  })
  const [isConnected, setIsConnected] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Handle Cognito callback
  useEffect(() => {
    if (window.location.search.includes('code=')) {
      handleCallback().then(success => {
        if (success) setAuthed(true)
      })
    }
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // --- Streaming via AgentCoreClient (typed SSE parsing) ---

  const streamAgentCore = useCallback(async (prompt: string) => {
    if (!agentCoreClient) return

    let content = ''
    const toolCalls: ToolCall[] = []
    const toolInputBuffers: Record<string, string> = {}

    const accessToken = getAccessToken() || 'local-dev-token'

    setMessages(prev => [...prev, { role: 'assistant', content: '', toolCalls: [] }])

    const onEvent = (event: StreamEvent) => {
      switch (event.type) {
        case 'text':
          content += event.content
          break
        case 'tool_use_start':
          toolCalls.push({ id: event.toolUseId, name: event.name, input: '' })
          toolInputBuffers[event.toolUseId] = ''
          break
        case 'tool_use_delta':
          if (toolInputBuffers[event.toolUseId] !== undefined) {
            toolInputBuffers[event.toolUseId] += event.input
          }
          break
        case 'tool_result': {
          const tc = toolCalls.find(t => t.id === event.toolUseId)
          if (tc) {
            tc.input = toolInputBuffers[event.toolUseId] || ''
            tc.result = event.result
          }
          break
        }
      }

      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content,
          toolCalls: [...toolCalls],
        }
        return updated
      })
    }

    await agentCoreClient.invoke(prompt, sessionId, accessToken, onEvent)
  }, [sessionId])

  // --- Streaming via direct fetch (local mode) ---

  const streamLocal = useCallback(async (prompt: string) => {
    const response = await fetch(`${agentUrl}/invocations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, runtimeSessionId: sessionId }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let assistantContent = ''

    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    while (reader) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })

      // Try to parse SSE data lines for strands format
      for (const line of chunk.split('\n')) {
        if (!line.startsWith('data: ')) {
          // Raw text fallback
          if (line.trim() && !line.startsWith(':')) {
            assistantContent += line
          }
          continue
        }
        try {
          const json = JSON.parse(line.substring(6))
          if (typeof json.data === 'string') {
            assistantContent += json.data
          }
        } catch {
          // Not JSON SSE — treat as raw text
          assistantContent += line.substring(6)
        }
      }

      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'assistant', content: assistantContent }
        return updated
      })
    }
  }, [sessionId])

  // --- Send message ---

  // AgentCore mode requires Cognito auth
  const needsAuth = isAgentCore && isAuthEnabled() && !authed

  const sendMessage = async () => {
    if (!input.trim() || isStreaming) return

    if (needsAuth) {
      login()
      return
    }

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsStreaming(true)

    try {
      if (isAgentCore) {
        await streamAgentCore(userMessage)
      } else {
        await streamLocal(userMessage)
      }
    } catch (error) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Error: ${error}` },
      ])
    } finally {
      setIsStreaming(false)
    }
  }

  const connectDatabase = () => {
    const prompt =
      `Connect to the database: host=${dbConfig.host}, port=${dbConfig.port}, ` +
      `database=${dbConfig.database}, user=${dbConfig.user}, ` +
      `driver_type=${dbConfig.driverType}. Then scan the metadata to discover the schema.`
    setInput(prompt)
    setIsConnected(true)
  }

  return (
    <div className="flex h-screen" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
      {/* Sidebar */}
      <aside
        className="flex flex-col overflow-y-auto"
        style={{
          width: 300,
          padding: 20,
          backgroundColor: 'var(--surface-bg)',
          borderRight: '1px solid var(--border)',
        }}
      >
        {/* Backend mode indicator */}
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            borderRadius: 12,
            fontSize: 12,
            fontWeight: 600,
            marginBottom: 16,
            alignSelf: 'flex-start',
            border: `1px solid ${isAgentCore ? 'var(--orange)' : 'var(--teal)'}`,
            color: isAgentCore ? 'var(--orange)' : 'var(--teal)',
            backgroundColor: 'var(--surface-card)',
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              backgroundColor: isAgentCore ? 'var(--orange)' : 'var(--teal)',
            }}
          />
          {isAgentCore ? 'AgentCore Runtime' : 'Local Agent'}
        </div>

        <h2
          style={{
            margin: '0 0 16px',
            fontSize: 16,
            fontWeight: 600,
            color: 'var(--text-primary)',
          }}
        >
          Database Connection
        </h2>

        <div className="flex flex-col" style={{ gap: 8 }}>
          <input placeholder="Host" value={dbConfig.host}
            onChange={e => setDbConfig(p => ({ ...p, host: e.target.value }))}
            style={inputStyle} />
          <input placeholder="Port" value={dbConfig.port}
            onChange={e => setDbConfig(p => ({ ...p, port: e.target.value }))}
            style={inputStyle} />
          <input placeholder="Database" value={dbConfig.database}
            onChange={e => setDbConfig(p => ({ ...p, database: e.target.value }))}
            style={inputStyle} />
          <input placeholder="User" value={dbConfig.user}
            onChange={e => setDbConfig(p => ({ ...p, user: e.target.value }))}
            style={inputStyle} />
          <input placeholder="Password" type="password" value={dbConfig.password}
            onChange={e => setDbConfig(p => ({ ...p, password: e.target.value }))}
            style={inputStyle} />
          <select value={dbConfig.driverType}
            onChange={e => setDbConfig(p => ({ ...p, driverType: e.target.value }))}
            style={inputStyle}>
            <option value="postgresql">PostgreSQL</option>
            <option value="redshift">Redshift</option>
          </select>
          <button onClick={connectDatabase} style={buttonPrimary}>
            {isConnected ? 'Reconnect' : 'Connect & Discover Schema'}
          </button>
        </div>

        {isConnected && (
          <div
            style={{
              marginTop: 16,
              padding: '8px 12px',
              borderRadius: 6,
              backgroundColor: 'var(--surface-card)',
              border: '1px solid var(--teal)',
              color: 'var(--teal)',
              fontSize: 13,
            }}
          >
            Connected to <strong>{dbConfig.database || 'database'}</strong>
          </div>
        )}

        {/* Auth section */}
        {isAuthEnabled() && (
          <div style={{ marginTop: 'auto', paddingTop: 20, borderTop: '1px solid var(--border)' }}>
            {authed ? (
              <div style={{ fontSize: 13 }}>
                <div style={{ color: 'var(--text-secondary)', marginBottom: 8 }}>
                  {getUserInfo()?.email || 'Authenticated'}
                </div>
                <button onClick={logout} style={{ ...buttonSecondary, width: '100%' }}>
                  Sign out
                </button>
              </div>
            ) : (
              <button onClick={login} style={{ ...buttonPrimary, width: '100%' }}>
                Sign in with Cognito
              </button>
            )}
          </div>
        )}
      </aside>

      {/* Main chat area */}
      <main className="flex flex-col" style={{ flex: 1 }}>
        {/* Header */}
        <header
          style={{
            padding: '16px 24px',
            borderBottom: '1px solid var(--border)',
            backgroundColor: 'var(--surface-card)',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <h1
            style={{
              margin: 0,
              fontSize: 18,
              fontWeight: 700,
              color: 'var(--text-primary)',
            }}
          >
            Talk To Your Data
          </h1>
          <span
            style={{
              fontSize: 13,
              color: 'var(--teal)',
              fontWeight: 500,
            }}
          >
            phData Platform Agent
          </span>
        </header>

        {/* Messages */}
        <div
          className="flex-1 overflow-y-auto"
          style={{ padding: 24, backgroundColor: 'var(--surface-bg)' }}
        >
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', marginTop: 80 }}>
              {needsAuth ? (
                <>
                  <h3
                    style={{
                      color: 'var(--text-primary)',
                      fontSize: 20,
                      fontWeight: 600,
                      marginBottom: 12,
                    }}
                  >
                    Sign in to continue
                  </h3>
                  <p style={{ color: 'var(--text-secondary)', maxWidth: 440, margin: '0 auto' }}>
                    AgentCore Runtime requires authentication.
                    Sign in with your Cognito credentials to start querying.
                  </p>
                  <button
                    onClick={login}
                    style={{ ...buttonPrimary, marginTop: 24 }}
                  >
                    Sign in with Cognito
                  </button>
                </>
              ) : (
                <>
                  <h3
                    style={{
                      color: 'var(--text-primary)',
                      fontSize: 20,
                      fontWeight: 600,
                      marginBottom: 12,
                    }}
                  >
                    Connect to get started
                  </h3>
                  <p style={{ color: 'var(--text-secondary)', maxWidth: 440, margin: '0 auto' }}>
                    Enter your database credentials in the sidebar and click{' '}
                    <strong style={{ color: 'var(--text-primary)' }}>Connect & Discover Schema</strong>.
                    The agent will scan your tables, columns, and relationships, then you can ask
                    questions in plain English.
                  </p>
                  <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 20 }}>
                    Supports PostgreSQL and Redshift. Read-only — your data is never modified.
                  </p>
                </>
              )}
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} style={{ marginBottom: 16 }}>
              {/* Role label */}
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase' as const,
                  letterSpacing: '0.05em',
                  color: msg.role === 'user' ? 'var(--blue)' : 'var(--teal)',
                  marginBottom: 4,
                  marginLeft: msg.role === 'user' ? 'auto' : 0,
                  maxWidth: '80%',
                  textAlign: msg.role === 'user' ? 'right' : 'left',
                }}
              >
                {msg.role === 'user' ? 'You' : 'Agent'}
              </div>

              {/* Message bubble */}
              <div
                style={{
                  padding: '12px 16px',
                  borderRadius: 8,
                  backgroundColor:
                    msg.role === 'user' ? 'var(--blue)' : 'var(--surface-card)',
                  color:
                    msg.role === 'user' ? '#FFFFFF' : 'var(--text-primary)',
                  maxWidth: '80%',
                  marginLeft: msg.role === 'user' ? 'auto' : 0,
                  whiteSpace: 'pre-wrap',
                  fontSize: 14,
                  lineHeight: 1.6,
                  border:
                    msg.role === 'assistant'
                      ? '1px solid var(--border)'
                      : 'none',
                }}
              >
                {msg.content}
                {msg.content === '' && isStreaming && i === messages.length - 1 && (
                  <span style={{ color: 'var(--text-muted)' }}>Thinking...</span>
                )}
              </div>

              {/* Tool calls (AgentCore mode) */}
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div style={{ marginTop: 8, marginLeft: 16 }}>
                  {msg.toolCalls.map(tc => (
                    <div
                      key={tc.id}
                      style={{
                        padding: '6px 10px',
                        borderRadius: 4,
                        backgroundColor: 'var(--surface-bg)',
                        border: '1px solid var(--border)',
                        fontSize: 12,
                        color: 'var(--text-secondary)',
                        marginBottom: 4,
                        fontFamily: 'monospace',
                      }}
                    >
                      <span style={{ color: 'var(--orange)', fontWeight: 600 }}>
                        {tc.name}
                      </span>
                      {tc.result && (
                        <span style={{ color: 'var(--teal)', marginLeft: 8 }}>
                          done
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            gap: 8,
            backgroundColor: 'var(--surface-card)',
          }}
        >
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendMessage()}
            placeholder="Ask a question about your data..."
            disabled={isStreaming}
            style={{ ...inputStyle, flex: 1 }}
          />
          <button
            onClick={sendMessage}
            disabled={isStreaming}
            style={{
              ...buttonPrimary,
              opacity: isStreaming ? 0.5 : 1,
              cursor: isStreaming ? 'not-allowed' : 'pointer',
            }}
          >
            {isStreaming ? 'Thinking...' : 'Send'}
          </button>
        </div>
      </main>
    </div>
  )
}

// --- Shared styles ---

const inputStyle: React.CSSProperties = {
  padding: '8px 12px',
  border: '1px solid var(--border)',
  borderRadius: 6,
  fontSize: 14,
  backgroundColor: 'var(--surface-input)',
  color: 'var(--text-primary)',
  outline: 'none',
}

const buttonPrimary: React.CSSProperties = {
  padding: '10px 20px',
  backgroundColor: 'var(--blue)',
  color: '#FFFFFF',
  border: 'none',
  borderRadius: 6,
  cursor: 'pointer',
  fontSize: 14,
  fontWeight: 600,
}

const buttonSecondary: React.CSSProperties = {
  padding: '8px 16px',
  backgroundColor: 'transparent',
  color: 'var(--text-secondary)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  cursor: 'pointer',
  fontSize: 13,
}
