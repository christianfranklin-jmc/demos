import { useState, useRef, useEffect } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  agent?: string
}

interface AgentConfig {
  id: string
  name: string
  description: string
  color: string
  icon: string
  placeholder: string
}

const AGENTS: AgentConfig[] = [
  {
    id: 'migration',
    name: 'Migration',
    description: 'Snowflake → Iceberg extraction, schema conversion, dbt scaffold',
    color: '#2E75B6',
    icon: '🔄',
    placeholder: 'e.g., "Connect to Snowflake and extract the schema for migration"',
  },
  {
    id: 'enrichment',
    name: 'Enrichment',
    description: 'RAG descriptions, DataZone publishing, semantic YAML',
    color: '#00B4A0',
    icon: '📝',
    placeholder: 'e.g., "Generate descriptions for all tables and columns"',
  },
  {
    id: 'quality',
    name: 'Quality',
    description: 'DQDL rules, data quality checks, quarantine, remediation',
    color: '#E67E22',
    icon: '✅',
    placeholder: 'e.g., "Run quality checks on FACT_REVENUE"',
  },
  {
    id: 'mapping',
    name: 'Mapping',
    description: 'Knowledge graph, entity extraction, dbt lineage',
    color: '#8E44AD',
    icon: '🗺️',
    placeholder: 'e.g., "Build a knowledge graph from the schema metadata"',
  },
  {
    id: 'query',
    name: 'Query',
    description: 'NL-to-SQL, semantic cache, self-correction, dbt metrics',
    color: '#27AE60',
    icon: '🔍',
    placeholder: 'e.g., "What are the top 5 clients by revenue?"',
  },
]

/**
 * Platform Agent — Semantic Layer Agents
 *
 * Multi-agent chat interface for Snowflake → AWS migration.
 * Each agent has its own Runtime endpoint and tool set.
 */
export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<AgentConfig>(AGENTS[4]) // Default: Query
  const [dbConfig, setDbConfig] = useState({
    host: '',
    port: '5432',
    database: '',
    user: '',
    password: '',
    driverType: 'snowflake',
  })
  const [isConnected, setIsConnected] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Each agent can have its own endpoint (or share one)
  const getAgentUrl = (agentId: string) => {
    const envKey = `VITE_${agentId.toUpperCase()}_AGENT_URL`
    return import.meta.env[envKey]
      || import.meta.env.VITE_AGENT_URL
      || 'http://localhost:8080'
  }

  const sendMessage = async () => {
    if (!input.trim() || isStreaming) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, {
      role: 'user', content: userMessage, agent: selectedAgent.id,
    }])
    setIsStreaming(true)

    try {
      const agentUrl = getAgentUrl(selectedAgent.id)
      const response = await fetch(`${agentUrl}/invocations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: userMessage }),
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let assistantContent = ''

      setMessages(prev => [...prev, {
        role: 'assistant', content: '', agent: selectedAgent.id,
      }])

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
            agent: selectedAgent.id,
          }
          return updated
        })
      }
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${error}`,
        agent: selectedAgent.id,
      }])
    } finally {
      setIsStreaming(false)
    }
  }

  const connectDatabase = () => {
    const prompt = `Connect to the database: host=${dbConfig.host}, port=${dbConfig.port}, database=${dbConfig.database}, user=${dbConfig.user}, driver_type=${dbConfig.driverType}. Then scan the metadata to discover the schema.`
    setInput(prompt)
    setIsConnected(true)
  }

  const agentColor = selectedAgent.color

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'system-ui, sans-serif' }}>
      {/* Sidebar */}
      <aside style={{
        width: '300px', borderRight: '1px solid #e0e0e0',
        backgroundColor: '#f8f9fa', overflowY: 'auto', display: 'flex',
        flexDirection: 'column',
      }}>
        {/* Agent Selector */}
        <div style={{ padding: '16px', borderBottom: '1px solid #e0e0e0' }}>
          <h2 style={{ margin: '0 0 12px', fontSize: '16px', color: '#333' }}>
            Select Agent
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {AGENTS.map(agent => (
              <button
                key={agent.id}
                onClick={() => setSelectedAgent(agent)}
                style={{
                  padding: '8px 12px',
                  border: selectedAgent.id === agent.id
                    ? `2px solid ${agent.color}` : '1px solid #ddd',
                  borderRadius: '8px',
                  backgroundColor: selectedAgent.id === agent.id
                    ? `${agent.color}10` : 'white',
                  cursor: 'pointer',
                  textAlign: 'left',
                  fontSize: '13px',
                }}
              >
                <div style={{ fontWeight: 600 }}>
                  {agent.icon} {agent.name}
                </div>
                <div style={{ fontSize: '11px', color: '#666', marginTop: '2px' }}>
                  {agent.description}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Database Connection */}
        <div style={{ padding: '16px', flex: 1 }}>
          <h2 style={{ margin: '0 0 12px', fontSize: '16px', color: '#333' }}>
            Database Connection
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
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
              <option value="snowflake">Snowflake</option>
              <option value="postgresql">PostgreSQL</option>
              <option value="redshift">Redshift</option>
            </select>
            <button onClick={connectDatabase}
              style={{
                padding: '8px', backgroundColor: agentColor, color: 'white',
                border: 'none', borderRadius: '6px', cursor: 'pointer',
                fontSize: '13px',
              }}>
              {isConnected ? 'Reconnect' : 'Connect & Discover'}
            </button>
          </div>
        </div>
      </aside>

      {/* Main Chat */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <header style={{
          padding: '14px 20px', borderBottom: '1px solid #e0e0e0',
          backgroundColor: 'white', display: 'flex', alignItems: 'center', gap: '10px',
        }}>
          <span style={{ fontSize: '24px' }}>{selectedAgent.icon}</span>
          <div>
            <h1 style={{ margin: 0, fontSize: '18px', color: agentColor }}>
              {selectedAgent.name} Agent
            </h1>
            <p style={{ margin: 0, fontSize: '12px', color: '#888' }}>
              {selectedAgent.description}
            </p>
          </div>
        </header>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', color: '#888', marginTop: '40px' }}>
              <p style={{ fontSize: '48px' }}>{selectedAgent.icon}</p>
              <p>Select an agent and ask a question.</p>
              <p style={{ fontSize: '13px', color: '#aaa' }}>
                {selectedAgent.placeholder}
              </p>
            </div>
          )}
          {messages.map((msg, i) => {
            const msgAgent = AGENTS.find(a => a.id === msg.agent)
            return (
              <div key={i} style={{
                marginBottom: '12px',
                padding: '10px 14px',
                borderRadius: '8px',
                backgroundColor: msg.role === 'user' ? '#e3f2fd'
                  : `${msgAgent?.color || '#888'}08`,
                borderLeft: msg.role === 'assistant'
                  ? `3px solid ${msgAgent?.color || '#888'}` : 'none',
                maxWidth: '85%',
                marginLeft: msg.role === 'user' ? 'auto' : '0',
                whiteSpace: 'pre-wrap',
                fontSize: '13px',
                lineHeight: '1.6',
              }}>
                {msg.role === 'assistant' && msgAgent && (
                  <div style={{
                    fontSize: '11px', color: msgAgent.color,
                    fontWeight: 600, marginBottom: '4px',
                  }}>
                    {msgAgent.icon} {msgAgent.name} Agent
                  </div>
                )}
                {msg.content}
              </div>
            )
          })}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div style={{
          padding: '14px 20px', borderTop: '1px solid #e0e0e0',
          display: 'flex', gap: '8px', backgroundColor: 'white',
        }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendMessage()}
            placeholder={selectedAgent.placeholder}
            disabled={isStreaming}
            style={{ ...inputStyle, flex: 1 }}
          />
          <button onClick={sendMessage} disabled={isStreaming}
            style={{
              padding: '8px 16px', backgroundColor: isStreaming ? '#ccc' : agentColor,
              color: 'white', border: 'none', borderRadius: '6px',
              cursor: isStreaming ? 'not-allowed' : 'pointer', fontSize: '13px',
            }}>
            {isStreaming ? 'Thinking...' : 'Send'}
          </button>
        </div>
      </main>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  padding: '6px 10px',
  border: '1px solid #ddd',
  borderRadius: '6px',
  fontSize: '13px',
}
