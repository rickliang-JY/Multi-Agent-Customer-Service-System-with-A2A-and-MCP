# A2A Multi-Agent Customer Service System

Multi-agent customer service using Google A2A protocol + MCP for tool access.

## Architecture

```
User --> Router Agent (9000) --> Data Agent (9001) --> MCP Server (5000) --> SQLite DB
                             --> Support Agent (9002) -->
```

## Files

| File | Description |
|------|-------------|
| `mcp_server.py` | MCP server with 5 database tools |
| `a2a_client_testing.py` | 3 coordinated A2A agents |
| `test_mcp_server.py` | MCP server test suite |
| `support.db` | SQLite database |
| `requirements.txt` | Python dependencies |

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create `.env` file

Create a `.env` file in the project directory with:

```
GOOGLE_API_KEY=your_key
MCP_SERVER_URL=http://127.0.0.1:5000/mcp
```

### 3. Start MCP server

```bash
python mcp_server.py
```

### 4. Start A2A agents (new terminal)

```bash
python a2a_client_testing.py
```

## MCP Tools

| Tool | Usage |
|------|-------|
| `get_customer` | Get customer by ID |
| `list_customers` | List all/active/disabled customers |
| `update_customer` | Update customer info |
| `create_ticket` | Create support ticket |
| `get_customer_history` | Get customer's tickets |


## Example output:

SCENARIO 1: TASK ALLOCATION
   Query: 'I need help with my account, customer ID 1'
   Expected: Router -> Data Agent -> Router -> Support Agent -> Response


+--[Step 1] 22:43:31.350
| User --> Router Agent
| Type: REQUEST
| Content: I need help with my account, customer ID 1
+--------------------------------------------------

+--[Step 2] 22:43:33.157
| Router Agent --> Data Agent
| Type: DELEGATE
| Content: Get full customer info for ID 1 including tier and status
+--------------------------------------------------

+--[Step 3] 22:43:36.761
| Data Agent --> Router Agent
| Type: RESPONSE
| Content: Customer #1 (John Doe Updated) is an active customer. Email: john.updated@example.com, phone: 555-9999. The customer's tier is not explicitly available in the provided information. They were created on 2025-11-30.
+--------------------------------------------------

+--[Step 4] 22:43:38.219
| Router Agent --> Support Agent
| Type: DELEGATE
| Content: Handle support for customer John Doe. Email: john.updated@example.com, phone: 555-9999. Created on 2025-11-30. Tier is not explicitly available.
+--------------------------------------------------

+--[Step 5] 22:43:39.672
| Support Agent --> Router Agent
| Type: RESPONSE
| Content: Okay, I can help with that. I will update John Doe's contact information. What is his customer ID?

+--------------------------------------------------

+--[Step 6] 22:43:41.091
| Router Agent --> User
| Type: FINAL_RESPONSE
| Content: Okay, I've contacted support to help with your account, John Doe. They need your customer ID to proceed. Please provide that to them.

+--------------------------------------------------

Total Time: 9.74s

FINAL RESPONSE:

Okay, I've contacted support to help with your account, John Doe. They need your customer ID to proceed. Please provide that to them.




COMMUNICATION SUMMARY


   Total Steps: 6
   Agents Involved: 4
   Agents: User, Support Agent, Router Agent, Data Agent

FLOW DIAGRAM:
   [1] User -> Router Agent: REQUEST
   [2] Router Agent -> Data Agent: DELEGATE
   [3] Data Agent -> Router Agent: RESPONSE
   [4] Router Agent -> Support Agent: DELEGATE
   [5] Support Agent -> Router Agent: RESPONSE
   [6] Router Agent -> User: FINAL_RESPONSE



