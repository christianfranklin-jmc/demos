"""HTTP/SSE surface in front of the Strands agent.

Thin FastAPI layer that owns routing, SSE streaming, session-ID extraction,
and zip response generation. See docs/adr/015-dsa-agent-integration.md D8.
"""
