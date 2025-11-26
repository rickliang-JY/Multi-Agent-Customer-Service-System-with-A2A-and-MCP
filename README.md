# 🤖 Multi-Agent Customer Service System

> **ADSP 32028 - Applied Generative AI | Assignment 5**  
> University of Chicago | November 2025

A sophisticated multi-agent customer service system built with **LangGraph**, **MCP (Model Context Protocol)**, and **Agent-to-Agent (A2A) coordination**. The system demonstrates how multiple AI agents can collaborate to handle complex customer queries.

---

## 📋 Table of Contents

- [System Overview](#-system-overview)
- [Architecture Pipeline](#-architecture-pipeline)
- [Agent Descriptions](#-agent-descriptions)
- [MCP Integration](#-mcp-integration)
- [A2A Coordination Patterns](#-a2a-coordination-patterns)
- [Setup Instructions](#-setup-instructions)
- [Running the System](#-running-the-system)
- [Test Scenarios](#-test-scenarios)
- [Example Outputs](#-example-outputs)
- [Project Structure](#-project-structure)
- [Technical Details](#-technical-details)

---

## 🎯 System Overview

This system implements a **multi-agent architecture** where specialized AI agents collaborate to handle customer service requests:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MULTI-AGENT CUSTOMER SERVICE SYSTEM                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Customer Query ──▶ [Router Agent] ──▶ [Specialist Agents] ──▶ Response   │
│                                                                             │
│   ┌─────────────┐    ┌──────────────────┐    ┌─────────────────────────┐   │
│   │   Router    │    │  Customer Data   │    │    Support Agent        │   │
│   │   Agent     │───▶│     Agent        │───▶│  (Response Generation)  │   │
│   │(Orchestrator)│    │  (Data Access)   │    │                         │   │
│   └─────────────┘    └──────────────────┘    └─────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│                      ┌──────────────┐                                       │
│                      │  MCP Server  │                                       │
│                      │  (6 Tools)   │                                       │
│                      └──────────────┘                                       │
│                              │                                              │
│                              ▼                                              │
│                      ┌──────────────┐                                       │
│                      │   SQLite     │                                       │
│                      │  Database    │                                       │
│                      └──────────────┘                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Agent Orchestration** | Router agent coordinates specialist agents based on query intent |
| **MCP Protocol** | Standardized tool interface for database operations |
| **A2A Communication** | Agents exchange messages and share state |
| **LangGraph Workflow** | State machine for agent coordination |
| **LLM-Powered Decisions** | GPT-4o/Claude for intelligent routing and responses |

---

## 🔄 Architecture Pipeline

### Complete Request Flow

```
                                    CUSTOMER QUERY
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              1. ROUTER AGENT                                │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  • Receives customer query                                            │  │
│  │  • Analyzes intent using LLM                                          │  │
│  │  • Determines task type: data_retrieval | support | complex_multi_step│  │
│  │  • Routes to appropriate specialist agent                             │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
┌───────────────────────────────────┐     ┌───────────────────────────────────┐
│     2. CUSTOMER DATA AGENT        │     │       2. SUPPORT AGENT            │
│  ┌─────────────────────────────┐  │     │  ┌─────────────────────────────┐  │
│  │ • Extracts customer ID      │  │     │  │ • Handles general support   │  │
│  │ • Calls MCP tools           │  │     │  │ • May request data from     │  │
│  │ • Retrieves customer info   │  │     │  │   Customer Data Agent       │  │
│  │ • Fetches ticket history    │  │     │  │ • Generates responses       │  │
│  │ • Gets priority tickets     │  │     │  └─────────────────────────────┘  │
│  └─────────────────────────────┘  │     └───────────────────────────────────┘
└───────────────────────────────────┘                     │
                    │                                     │
                    ▼                                     │
┌───────────────────────────────────┐                     │
│          3. MCP SERVER            │                     │
│  ┌─────────────────────────────┐  │                     │
│  │ Tools:                      │  │                     │
│  │ • get_customer              │  │                     │
│  │ • list_customers            │  │                     │
│  │ • update_customer           │  │                     │
│  │ • create_ticket             │  │                     │
│  │ • get_customer_history      │  │                     │
│  │ • get_tickets_by_priority   │  │                     │
│  └─────────────────────────────┘  │                     │
└───────────────────────────────────┘                     │
                    │                                     │
                    ▼                                     │
┌───────────────────────────────────┐                     │
│        4. SQLITE DATABASE         │                     │
│  ┌─────────────────────────────┐  │                     │
│  │ Tables:                     │  │                     │
│  │ • customers (15 records)    │  │                     │
│  │ • tickets (25+ records)     │  │                     │
│  └─────────────────────────────┘  │                     │
└───────────────────────────────────┘                     │
                    │                                     │
                    └──────────────────┬──────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           5. SUPPORT AGENT                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  • Receives data from Customer Data Agent                             │  │
│  │  • Builds context from customer info + tickets                        │  │
│  │  • Generates personalized response using LLM                          │  │
│  │  • Returns final response to customer                                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                               FINAL RESPONSE
```

### LangGraph State Machine

```
                        ┌──────────────┐
                        │    START     │
                        └──────┬───────┘
                               │
                               ▼
                        ┌──────────────┐
                   ┌────│    ROUTER    │────┐
                   │    └──────────────┘    │
                   │                        │
          (data needed)            (support needed)
                   │                        │
                   ▼                        ▼
          ┌──────────────┐          ┌──────────────┐
          │CUSTOMER_DATA │─────────▶│   SUPPORT    │
          └──────────────┘          └──────────────┘
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │     END      │
                                    └──────────────┘
```

---

## 🤖 Agent Descriptions

### 1. Router Agent (Orchestrator)

The **brain** of the system that analyzes queries and coordinates other agents.

```python
class RouterAgent:
    """
    Responsibilities:
    - Analyze customer query intent
    - Determine task type (data_retrieval, support, complex_multi_step)
    - Route to appropriate specialist agent
    - Coordinate multi-agent workflows
    """
```

**Decision Process:**
```
Query: "Get customer information for ID 5"
                    │
                    ▼
        ┌───────────────────────┐
        │   LLM Analysis        │
        │   ─────────────────   │
        │   Keywords: "get",    │
        │   "customer", "ID"    │
        │   ─────────────────   │
        │   Task: data_retrieval│
        │   Agent: customer_data│
        └───────────────────────┘
                    │
                    ▼
        Route to Customer Data Agent
```

### 2. Customer Data Agent (Specialist)

Handles all **database operations** through MCP tools.

```python
class CustomerDataAgent:
    """
    Responsibilities:
    - Extract customer IDs from queries
    - Call appropriate MCP tools
    - Retrieve customer information
    - Fetch ticket history
    - Get priority-based ticket lists
    """
```

**Data Flow:**
```
Query: "Show high priority tickets"
                    │
                    ▼
        ┌───────────────────────┐
        │  Extract Parameters   │
        │  ─────────────────    │
        │  Priority: high       │
        │  Status: open         │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  MCP Tool Call        │
        │  ─────────────────    │
        │  get_tickets_by_      │
        │  priority(            │
        │    priority='high',   │
        │    status='open'      │
        │  )                    │
        └───────────────────────┘
                    │
                    ▼
        Return ticket data to state
```

### 3. Support Agent (Specialist)

**Generates final responses** using retrieved data and LLM.

```python
class SupportAgent:
    """
    Responsibilities:
    - Generate personalized customer responses
    - Use customer data and ticket history
    - Provide actionable recommendations
    - Format responses professionally
    """
```

**Response Generation:**
```
        ┌───────────────────────┐
        │   Input Context       │
        │   ─────────────────   │
        │   • Customer Query    │
        │   • Customer Data     │
        │   • Ticket History    │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   LLM Processing      │
        │   ─────────────────   │
        │   System Prompt:      │
        │   "Generate helpful,  │
        │   professional        │
        │   response..."        │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   Final Response      │
        │   ─────────────────   │
        │   "Hello [Name],      │
        │   Here is your        │
        │   account info..."    │
        └───────────────────────┘
```

---

## 🔧 MCP Integration

### MCP Server Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MCP SERVER                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│   │  get_customer   │  │ list_customers  │  │ update_customer │            │
│   │  ─────────────  │  │  ─────────────  │  │  ─────────────  │            │
│   │  Input:         │  │  Input:         │  │  Input:         │            │
│   │   customer_id   │  │   status        │  │   customer_id   │            │
│   │  Output:        │  │   limit         │  │   data (dict)   │            │
│   │   customer dict │  │  Output:        │  │  Output:        │            │
│   │                 │  │   customer list │  │   updated dict  │            │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘            │
│                                                                             │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│   │  create_ticket  │  │get_customer_    │  │get_tickets_by_  │            │
│   │  ─────────────  │  │    history      │  │    priority     │            │
│   │  Input:         │  │  ─────────────  │  │  ─────────────  │            │
│   │   customer_id   │  │  Input:         │  │  Input:         │            │
│   │   issue         │  │   customer_id   │  │   priority      │            │
│   │   priority      │  │  Output:        │  │   status        │            │
│   │  Output:        │  │   customer +    │  │  Output:        │            │
│   │   ticket dict   │  │   tickets list  │  │   tickets list  │            │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘            │
│                                                                             │
│                              │                                              │
│                              ▼                                              │
│                    ┌─────────────────┐                                      │
│                    │  SQLite Driver  │                                      │
│                    │  (Row Factory)  │                                      │
│                    └─────────────────┘                                      │
│                              │                                              │
│                              ▼                                              │
│                    ┌─────────────────┐                                      │
│                    │   support.db    │                                      │
│                    └─────────────────┘                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Database Schema

```sql
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATABASE SCHEMA                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   CUSTOMERS TABLE                        TICKETS TABLE                      │
│   ─────────────────                      ─────────────────                  │
│   ┌─────────────────┐                    ┌─────────────────┐                │
│   │ id (PK)         │◄───────────────────│ customer_id (FK)│                │
│   │ name            │                    │ id (PK)         │                │
│   │ email           │                    │ issue           │                │
│   │ phone           │                    │ status          │                │
│   │ status          │                    │ priority        │                │
│   │ created_at      │                    │ created_at      │                │
│   │ updated_at      │                    └─────────────────┘                │
│   └─────────────────┘                                                       │
│                                                                             │
│   Status: active | disabled              Status: open | in_progress |       │
│                                                   resolved                  │
│                                          Priority: low | medium | high      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔀 A2A Coordination Patterns

### Pattern 1: Simple Data Retrieval

```
Query: "Get customer info for ID 5"

┌────────┐     ┌───────────────┐     ┌─────────┐     ┌───────┐
│ Router │────▶│ Customer Data │────▶│ Support │────▶│  END  │
└────────┘     └───────────────┘     └─────────┘     └───────┘
    │                  │                   │
    │ "Route to       │ "Retrieved        │ "Generated
    │  data agent"    │  customer 5"      │  response"
```

### Pattern 2: Support with Data Request

```
Query: "I need help with my account, ID 3"

┌────────┐     ┌─────────┐     ┌───────────────┐     ┌─────────┐     ┌───────┐
│ Router │────▶│ Support │────▶│ Customer Data │────▶│ Support │────▶│  END  │
└────────┘     └─────────┘     └───────────────┘     └─────────┘     └───────┘
    │              │                   │                   │
    │ "Route to   │ "Need customer   │ "Retrieved        │ "Generated
    │  support"   │  data first"     │  Bob Johnson"     │  response"
```

### Pattern 3: Complex Multi-Step Query

```
Query: "Show all high-priority tickets for active customers"

┌────────┐     ┌───────────────┐     ┌───────────────┐     ┌─────────┐     ┌───────┐
│ Router │────▶│ Customer Data │────▶│ Customer Data │────▶│ Support │────▶│  END  │
└────────┘     └───────────────┘     └───────────────┘     └─────────┘     └───────┘
    │                  │                     │                   │
    │ "Complex        │ "Get high          │ "Get active       │ "Generated
    │  multi-step"    │  priority tickets" │  customers"       │  report"
```

### State Management

```python
class AgentState(TypedDict):
    """Shared state across all agents"""
    
    # Input
    query: str                              # Original customer query
    
    # Agent Communication
    messages: List[Dict]                    # Message history between agents
    current_agent: str                      # Currently active agent
    next_agent: Optional[str]               # Next agent to route to
    
    # Data Storage
    customer_data: Optional[Dict]           # Retrieved customer info
    tickets: Optional[List[Dict]]           # Retrieved tickets
    
    # Output
    final_response: str                     # Generated response
    
    # Metadata
    coordination_log: List[str]             # Agent activity log
    task_type: Optional[str]                # Classified task type
```

---

## 🚀 Setup Instructions

### Prerequisites

- Python 3.9+ 
- Conda or venv
- OpenAI API Key (or Anthropic API Key)

### Step 1: Create Environment

**Using Conda (Recommended):**
```bash
conda create -n multi_agent python=3.10 -y
conda activate multi_agent
```

**Using venv:**
```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
.\venv\Scripts\Activate.ps1  # Windows PowerShell
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Set API Key

**Windows PowerShell:**
```powershell
$env:OPENAI_API_KEY="sk-your-openai-key"
```

**macOS/Linux:**
```bash
export OPENAI_API_KEY="sk-your-openai-key"
```

### Step 4: Initialize Database

```bash
python database_setup.py
# Enter 'y' to insert sample data
# Enter 'y' to run sample queries
```

Or use quick setup:
```bash
python init_database.py
```

---

## ▶️ Running the System

### Run All Test Scenarios

```bash
python test_scenarios.py
```

### Run with Output Logging

```bash
# PowerShell
python test_scenarios.py | Tee-Object -FilePath "test_output.txt"

# macOS/Linux
python test_scenarios.py | tee test_output.txt
```

### Run Individual Queries

```python
from multi_agent_system import process_query

# Simple query
result = process_query("Get customer information for ID 5")
print(result['response'])

# Complex query
result = process_query("Show all high-priority tickets for active customers")
print(result['response'])
```

---

## 🧪 Test Scenarios

| # | Scenario | Query | Tests |
|---|----------|-------|-------|
| 1 | Simple Query | "Get customer information for ID 5" | Single agent, direct MCP call |
| 2 | Task Allocation | "I need help with my account, customer ID 3" | Multi-agent coordination |
| 3 | Account Upgrade | "I'm customer 1 and need help upgrading" | Context-aware response |
| 4 | Complex Query | "Show all active customers with high priority tickets" | Multiple MCP calls |
| 5 | Escalation | "I've been charged twice! Urgent, ID 2" | Priority detection |
| 6 | Multi-Intent | "Update my email and show ticket history" | Parallel task handling |
| 7 | Negotiation | "Cancel subscription but having billing issues" | Multiple intents |
| 8 | Data Aggregation | "Status of all high-priority tickets for active customers" | Full report generation |

---

## 📤 Example Outputs

### Scenario 1: Simple Query

```
Query: Get customer information for ID 5

COORDINATION LOG:
────────────────────────────────────────────────────────────────────
  [ROUTER] Analysis: data_retrieval, Agents needed: ['customer_data']
  [ROUTER] Routing to Customer Data Agent
  [CUSTOMER DATA] Retrieved customer 5: Charlie Brown
  [CUSTOMER DATA] Forwarding to Support Agent
  [SUPPORT] Using single customer data
  [SUPPORT] Response generated - completing workflow
────────────────────────────────────────────────────────────────────

FINAL RESPONSE:
────────────────────────────────────────────────────────────────────
Here is the detailed information for the customer with ID 5:

- **Name:** Charlie Brown
- **Email:** charlie.brown@email.com
- **Phone:** +1-555-0105
- **Status:** Active
- **Account Created On:** November 24, 2025

If you need further assistance, please let me know!
────────────────────────────────────────────────────────────────────
```

### Scenario 4: Complex Query

```
Query: Show me all active customers who have high priority open tickets

COORDINATION LOG:
────────────────────────────────────────────────────────────────────
  [ROUTER] Analysis: complex_multi_step, Agents needed: ['customer_data']
  [CUSTOMER DATA] Retrieved 8 high priority tickets
  [CUSTOMER DATA] Retrieved 12 active customers
  [SUPPORT] Using customer list data (12 customers)
  [SUPPORT] Using ticket data (8 tickets)
  [SUPPORT] Response generated - completing workflow
────────────────────────────────────────────────────────────────────

FINAL RESPONSE:
────────────────────────────────────────────────────────────────────
Here is the list of active customers with high priority open tickets:

| # | Customer Name  | Issue                              | Status | Priority |
|---|----------------|---------------------------------------|--------|----------|
| 1 | John Doe       | Urgent: System access problems        | Open   | High     |
| 2 | John Doe       | Cannot login to account               | Open   | High     |
| 3 | Charlie Brown  | Critical billing error                | Open   | High     |
| 4 | Edward Norton  | Service outage impacting business     | Open   | High     |
| 5 | Edward Norton  | Payment processing failing            | Open   | High     |

**Summary:**
- Total active customers with high priority tickets: 3
- Total high priority open tickets: 5
- Customers with multiple tickets: John Doe (2), Edward Norton (2)
────────────────────────────────────────────────────────────────────
```

### Scenario 8: Data Aggregation Report

```
Query: What's the status of all high-priority tickets for active customers?

COORDINATION LOG:
────────────────────────────────────────────────────────────────────
  [ROUTER] Analysis: data_retrieval, Agents needed: ['customer_data']
  [CUSTOMER DATA] Retrieved 11 high priority tickets
  [CUSTOMER DATA] Retrieved 12 active customers
  [SUPPORT] Using customer list data (12 customers)
  [SUPPORT] Using ticket data (11 tickets)
  [SUPPORT] Response generated - completing workflow
────────────────────────────────────────────────────────────────────

FINAL RESPONSE:
────────────────────────────────────────────────────────────────────
Here is the status of all high-priority tickets for active customers:

| #  | Customer        | Issue                                    | Status      | Priority |
|----|-----------------|------------------------------------------|-------------|----------|
| 1  | John Doe        | Urgent: System access problems           | Open        | High     |
| 2  | Charlie Brown   | Critical billing error                   | Open        | High     |
| 3  | Edward Norton   | Service outage impacting business        | Open        | High     |
| 4  | John Doe        | Cannot login to account                  | Open        | High     |
| 5  | Alice Williams  | Database connection timeout errors       | In Progress | High     |
| 6  | Edward Norton   | Payment processing failing               | Open        | High     |
| 7  | Hannah Lee      | Critical security vulnerability found    | In Progress | High     |
| 8  | Laura Martinez  | Website completely down                  | Resolved    | High     |

**Summary:**
- Total high-priority tickets: 11
- Open: 8
- In Progress: 2
- Resolved: 1

If you need further assistance or details, please let me know!
────────────────────────────────────────────────────────────────────
```

---

## 📁 Project Structure

```
multi-agent-customer-service/
│
├── 📄 multi_agent_system.py     # Main agent system (LangGraph)
├── 📄 mcp_server.py             # MCP server with 6 database tools
├── 📄 database_setup.py         # Database initialization (official)
├── 📄 init_database.py          # Quick database setup
├── 📄 test_scenarios.py         # 8 comprehensive test scenarios
├── 📄 view_database.py          # Database viewer utility
│
├── 📄 requirements.txt          # Python dependencies
├── 📄 setup.sh                  # Unix setup script
│
├── 📄 README.md                 # This file
├── 📄 README_CN.md              # Chinese documentation
├── 📄 QUICKSTART.md             # Quick start guide
├── 📄 ARCHITECTURE.md           # Detailed architecture
├── 📄 CONCLUSION.md             # Learnings and challenges
├── 📄 TROUBLESHOOTING.md        # Common issues and solutions
│
├── 📓 multi_agent_system.ipynb  # Google Colab notebook
│
└── 📊 support.db                # SQLite database (generated)
```

---

## 🔧 Technical Details

### Technology Stack

| Component | Technology |
|-----------|------------|
| Orchestration | LangGraph |
| LLM | OpenAI GPT-4o / Anthropic Claude |
| Protocol | MCP (Model Context Protocol) |
| Database | SQLite |
| Language | Python 3.10+ |

### Key Dependencies

```
langchain>=0.3.0
langchain-openai>=0.3.0
langgraph>=0.2.0
openai>=1.0.0
```

### Performance Metrics

| Metric | Value |
|--------|-------|
| Simple Query | 6-12 messages |
| Complex Query | 12-28 messages |
| Response Time | 5-15 seconds |
| Success Rate | 100% |

---

## 📚 References

- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [OpenAI API](https://platform.openai.com/docs)
- [Anthropic API](https://docs.anthropic.com/)

---

## 👨‍💻 Author

**ADSP 32028 - Applied Generative AI**  
University of Chicago  
November 2025

---

## 📝 License

This project is for educational purposes as part of the ADSP 32028 course.
