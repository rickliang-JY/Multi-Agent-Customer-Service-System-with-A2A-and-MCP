# A2A Multi-Agent Customer Service System

A multi-agent customer service system demonstrating **Agent-to-Agent (A2A)** protocol coordination with **Model Context Protocol (MCP)** integration.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Query                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Router/Orchestrator                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • Query Analysis (intent detection, entity extraction) │    │
│  │  • Task Decomposition (sub-task creation)               │    │
│  │  • Agent Coordination (A2A protocol)                    │    │
│  │  • Response Aggregation                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │ A2A Protocol                  │ A2A Protocol
              ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│   Customer Data Agent    │    │     Support Agent        │
│   (Port 8001)            │    │     (Port 8002)          │
│                          │    │                          │
│  Skills:                 │    │  Skills:                 │
│  • get_customer          │    │  • generate_response     │
│  • list_customers        │    │  • format_data           │
│  • update_customer       │    │  • handle_complaint      │
│  • get_customer_history  │    │                          │
│  • get_tickets_by_priority│   │  Generates professional  │
└──────────────────────────┘    │  email-style responses   │
              │                 │  using OpenAI GPT-4o-mini│
              │ MCP Protocol    └──────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       MCP Server (Port 8000)                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Tools:                                                  │    │
│  │  • get_customer        • list_customers                 │    │
│  │  • update_customer     • get_customer_history           │    │
│  │  • create_ticket       • get_tickets_by_priority        │    │
│  │  • update_ticket                                        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SQLite Database                               │
│                    (support.db)                                  │
│  Tables: customers, tickets                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Features

### A2A Protocol Implementation
- **Agent Cards**: Each agent exposes `/.well-known/agent-card.json` describing capabilities
- **JSON-RPC 2.0**: Standard message format for agent communication
- **Task Management**: Async task creation, status tracking, and artifact handling

### MCP Protocol Integration
- **Tool Discovery**: `POST /tools/list` returns available tools
- **Tool Execution**: `POST /tools/call` executes tools with parameters
- **Database Operations**: CRUD operations on customers and tickets

### Support Agent Features
- **Email-Style Responses**: Generates professional customer service emails
- **LLM-Powered**: Uses OpenAI GPT-4o-mini for intelligent responses
- **Context-Aware**: Personalizes responses based on customer data

### Orchestration Patterns

| Pattern | Description |
|---------|-------------|
| **Simple Query** | Single agent, straightforward MCP call |
| **Coordinated** | Multiple agents coordinate: data fetch + response |
| **Negotiation** | Agents negotiate when complex queries detected |
| **Escalation** | Urgent queries routed with HIGH priority |
| **Multi-Intent** | Parallel task execution for multiple requests |

##  Project Structure

```
├── orchestrator.py          # Main orchestrator/router agent
├── customer_data_agent.py   # Customer data A2A agent
├── support_agent.py         # Support response A2A agent
├── mcp_server.py            # MCP server with database tools
├── database_setup.py        # Database initialization script
├── run_servers.py           # Start all servers
├── test_scenarios.py        # Comprehensive test suite
├── requirements.txt         # Python dependencies
├── support.db               # SQLite database
└── README.md                # This file
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Requirements:**
```
a2a-sdk[http-server]>=0.3.0
starlette>=0.38.0
sse-starlette>=1.6.0
fastapi>=0.115.0
uvicorn>=0.30.0
httpx>=0.27.0
sqlalchemy>=2.0.0
pydantic>=2.0.0
openai>=1.0.0
```

### 2. Set Environment Variables

```bash
# Windows
set OPENAI_API_KEY=your-openai-api-key

# Linux/Mac
export OPENAI_API_KEY=your-openai-api-key
```

### 3. Initialize Database

```bash
python database_setup.py
# Choose 'y' to create sample data
```

### 4. Start All Servers

```bash
python run_servers.py
```

Output:
```
Starting A2A Multi-Agent Customer Service System...
============================================================
[START] MCP Server on port 8000...
   [OK] MCP Server started (PID: 12345)
[START] Customer Data Agent on port 8001...
   [OK] Customer Data Agent started (PID: 12346)
[START] Support Agent on port 8002...
   [OK] Support Agent started (PID: 12347)
============================================================
[OK] 3/3 servers running

Server URLs:
   - MCP Server: http://localhost:8000
   - Customer Data Agent: http://localhost:8001
   - Support Agent: http://localhost:8002
```

### 5. Run Tests

```bash
python test_scenarios.py
```

### 6. Interactive Mode

```bash
python orchestrator.py
> demo    # Run all 5 test scenarios
> Get customer information for ID 5
> I've been charged twice, please refund immediately!
> quit
```


## API Endpoints

### MCP Server (Port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/tools/list` | POST | List available tools |
| `/tools/call` | POST | Execute a tool |

**Available Tools:**
- `get_customer` - Get customer by ID
- `list_customers` - List customers with filters
- `update_customer` - Update customer info
- `get_customer_history` - Get customer with tickets
- `create_ticket` - Create support ticket
- `update_ticket` - Update ticket status
- `get_tickets_by_priority` - Get tickets by priority level

### A2A Agents (Ports 8001, 8002)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent-card.json` | GET | Agent capabilities |
| `/` | POST | Send message (JSON-RPC) |

**A2A Message Format:**
```json
{
  "jsonrpc": "2.0",
  "id": "unique-id",
  "method": "message/send",
  "params": {
    "message": {
      "messageId": "uuid",
      "role": "user",
      "parts": [{"kind": "text", "text": "Your query here"}]
    }
  }
}
```

