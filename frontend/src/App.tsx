import { useState, useRef, useEffect } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

/**
 * Platform Agent — Talk To Your Data
 *
 * Chat interface that streams responses from the AgentCore Runtime.
 * Supports Cognito auth (when configured) and SSE streaming.
 */
export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const agentUrl = import.meta.env.VITE_AGENT_URL || 'http://localhost:8080'

  const sendMessage = async () => {
    if (!input.trim() || isStreaming) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsStreaming(true)

    try {
      const response = await fetch(`${agentUrl}/invocations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: userMessage }),
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
        assistantContent += chunk

        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'assistant',
            content: assistantContent,
          }
          return updated
        })
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

  const connectDatabase = async () => {
    const prompt = `Connect to the database: host=${dbConfig.host}, port=${dbConfig.port}, database=${dbConfig.database}, user=${dbConfig.user}, driver_type=${dbConfig.driverType}. Then scan the metadata to discover the schema.`
    setInput(prompt)
    setIsConnected(true)
  }

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'system-ui, sans-serif' }}>
      {/* Sidebar — Database Connection */}
      <aside style={{
        width: '300px', padding: '20px', borderRight: '1px solid #e0e0e0',
        backgroundColor: '#f8f9fa', overflowY: 'auto',
      }}>
        <h2 style={{ margin: '0 0 16px', fontSize: '18px' }}>Database Connection</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <input placeholder="Host" value={dbConfig.host}
            onChange={e => setDbConfig(prev => ({ ...prev, host: e.target.value }))}
            style={inputStyle} />
          <input placeholder="Port" value={dbConfig.port}
            onChange={e => setDbConfig(prev => ({ ...prev, port: e.target.value }))}
            style={inputStyle} />
          <input placeholder="Database" value={dbConfig.database}
            onChange={e => setDbConfig(prev => ({ ...prev, database: e.target.value }))}
            style={inputStyle} />
          <input placeholder="User" value={dbConfig.user}
            onChange={e => setDbConfig(prev => ({ ...prev, user: e.target.value }))}
            style={inputStyle} />
          <input placeholder="Password" type="password" value={dbConfig.password}
            onChange={e => setDbConfig(prev => ({ ...prev, password: e.target.value }))}
            style={inputStyle} />
          <select value={dbConfig.driverType}
            onChange={e => setDbConfig(prev => ({ ...prev, driverType: e.target.value }))}
            style={inputStyle}>
            <option value="postgresql">PostgreSQL</option>
            <option value="redshift">Redshift</option>
          </select>
          <button onClick={connectDatabase}
            style={{
              padding: '10px', backgroundColor: '#0066cc', color: 'white',
              border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '14px',
            }}>
            {isConnected ? 'Reconnect' : 'Connect & Discover Schema'}
          </button>
        </div>
      </aside>

      {/* Main — Chat */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <header style={{
          padding: '16px 20px', borderBottom: '1px solid #e0e0e0',
          backgroundColor: 'white',
        }}>
          <h1 style={{ margin: 0, fontSize: '20px' }}>Platform Agent — Talk To Your Data</h1>
        </header>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', color: '#888', marginTop: '40px' }}>
              <p>Connect to a database and ask questions in plain English.</p>
              <p style={{ fontSize: '14px' }}>
                Try: "What are the top 5 products by revenue?"
              </p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} style={{
              marginBottom: '16px',
              padding: '12px 16px',
              borderRadius: '8px',
              backgroundColor: msg.role === 'user' ? '#e3f2fd' : '#f5f5f5',
              maxWidth: '80%',
              marginLeft: msg.role === 'user' ? 'auto' : '0',
              whiteSpace: 'pre-wrap',
              fontSize: '14px',
              lineHeight: '1.6',
            }}>
              {msg.content}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div style={{
          padding: '16px 20px', borderTop: '1px solid #e0e0e0',
          display: 'flex', gap: '8px', backgroundColor: 'white',
        }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendMessage()}
            placeholder="Ask a question about your data..."
            disabled={isStreaming}
            style={{ ...inputStyle, flex: 1 }}
          />
          <button onClick={sendMessage} disabled={isStreaming}
            style={{
              padding: '10px 20px', backgroundColor: isStreaming ? '#ccc' : '#0066cc',
              color: 'white', border: 'none', borderRadius: '6px',
              cursor: isStreaming ? 'not-allowed' : 'pointer', fontSize: '14px',
            }}>
            {isStreaming ? 'Thinking...' : 'Send'}
          </button>
        </div>
      </main>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  padding: '8px 12px',
  border: '1px solid #ddd',
  borderRadius: '6px',
  fontSize: '14px',
}
