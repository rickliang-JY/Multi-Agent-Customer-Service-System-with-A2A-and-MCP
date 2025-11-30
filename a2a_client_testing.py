# A2A Multi-Agent Customer Service System - Advanced Version
# Supports complex agent coordination, task allocation, and multi-step communication

import os
import asyncio
import threading
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

import httpx
import uvicorn
import nest_asyncio
from dotenv import load_dotenv
from termcolor import colored

# Google ADK imports
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory import InMemoryMemoryService
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from google.adk.tools import FunctionTool

# A2A imports
from google.adk.a2a.executor.a2a_agent_executor import (
    A2aAgentExecutor,
    A2aAgentExecutorConfig,
)
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.apps import A2AStarletteApplication
from a2a.types import AgentCard, AgentCapabilities, AgentSkill

nest_asyncio.apply()
load_dotenv()

# ============================================================
# Configuration
# ============================================================

os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'FALSE'

MCP_SERVER_URL = os.getenv('MCP_SERVER_URL', 'http://127.0.0.1:5000/mcp')

# A2A ports
CUSTOMER_DATA_AGENT_PORT = 9001
SUPPORT_AGENT_PORT = 9002
ROUTER_AGENT_PORT = 9000

print(f"[OK] MCP Server URL: {MCP_SERVER_URL}")

# ============================================================
# Communication Tracker
# ============================================================

class CommunicationTracker:
    """Track communication between agents"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.logs = []
            cls._instance.enabled = True
            cls._instance.step_counter = 0
        return cls._instance
    
    def log(self, from_agent: str, to_agent: str, message_type: str, content: str):
        """Record a communication event"""
        if not self.enabled:
            return
        
        self.step_counter += 1
        entry = {
            "step": self.step_counter,
            "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "from": from_agent,
            "to": to_agent,
            "type": message_type,
            "content": content[:300] + "..." if len(content) > 300 else content
        }
        self.logs.append(entry)
        
        # Real-time print
        self._print_entry(entry)
    
    def _print_entry(self, entry: dict):
        """Print communication entry in real-time"""
        step = entry["step"]
        time_str = entry["time"]
        from_agent = entry["from"]
        to_agent = entry["to"]
        msg_type = entry["type"]
        content = entry["content"]
        
        # Select color based on agent
        if "Router" in from_agent:
            color = "green"
        elif "Data" in from_agent:
            color = "cyan"
        elif "Support" in from_agent:
            color = "yellow"
        elif "MCP" in to_agent or "MCP" in from_agent:
            color = "blue"
        elif "User" in from_agent:
            color = "white"
        else:
            color = "magenta"
        
        # Arrow direction based on message type
        if "REQUEST" in msg_type or "DELEGATE" in msg_type or "CALL" in msg_type:
            arrow = "-->"
        else:
            arrow = "<--"
        
        print(colored(f"\n+--[Step {step}] {time_str}", "white"))
        print(colored(f"| {from_agent} {arrow} {to_agent}", color, attrs=["bold"]))
        print(colored(f"| Type: {msg_type}", color))
        print(colored(f"| Content: {content}", "white"))
        print(colored(f"+{'-' * 50}", "white"))
    
    def reset(self):
        """Reset logs"""
        self.logs = []
        self.step_counter = 0
    
    def print_summary(self):
        """Print communication summary"""
        if not self.logs:
            print(colored("   No communication logs recorded", "yellow"))
            return
        
        print(colored("\n" + "=" * 60, "magenta"))
        print(colored("COMMUNICATION SUMMARY", "magenta", attrs=["bold"]))
        print(colored("=" * 60, "magenta"))
        
        # Statistics
        agents_involved = set()
        for entry in self.logs:
            agents_involved.add(entry["from"])
            agents_involved.add(entry["to"])
        
        print(f"\n   Total Steps: {len(self.logs)}")
        print(f"   Agents Involved: {len(agents_involved)}")
        print(f"   Agents: {', '.join(agents_involved)}")
        
        # Flow diagram
        print(colored("\nFLOW DIAGRAM:", "cyan", attrs=["bold"]))
        for entry in self.logs:
            arrow = "->" if "REQUEST" in entry["type"] or "DELEGATE" in entry["type"] else "<-"
            print(f"   [{entry['step']}] {entry['from']} {arrow} {entry['to']}: {entry['type']}")
        
        print(colored("\n" + "=" * 60, "magenta"))


# Global tracker instance
tracker = CommunicationTracker()

# ============================================================
# MCP Toolset
# ============================================================

mcp_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=MCP_SERVER_URL,
        timeout=60
    )
)

# ============================================================
# Agent Internal Communication Tools
# ============================================================

# HTTP client for inter-agent communication
agent_client = httpx.AsyncClient(timeout=60.0)

async def call_data_agent(query: str) -> str:
    """Router calls Customer Data Agent"""
    tracker.log("Router Agent", "Data Agent", "DELEGATE", query)
    
    task_id = f"t-{int(time.time()*1000)}"
    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "id": task_id,
        "params": {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": query}],
                "messageId": task_id,
            }
        }
    }
    
    resp = await agent_client.post(f'http://localhost:{CUSTOMER_DATA_AGENT_PORT}', json=payload)
    result = resp.json()
    
    # Extract text
    text = extract_text_from_response(result)
    tracker.log("Data Agent", "Router Agent", "RESPONSE", text)
    
    return text


async def call_support_agent(query: str) -> str:
    """Router calls Support Agent"""
    tracker.log("Router Agent", "Support Agent", "DELEGATE", query)
    
    task_id = f"t-{int(time.time()*1000)}"
    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "id": task_id,
        "params": {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": query}],
                "messageId": task_id,
            }
        }
    }
    
    resp = await agent_client.post(f'http://localhost:{SUPPORT_AGENT_PORT}', json=payload)
    result = resp.json()
    
    text = extract_text_from_response(result)
    tracker.log("Support Agent", "Router Agent", "RESPONSE", text)
    
    return text


def extract_text_from_response(result: dict) -> str:
    """Extract text from A2A response"""
    if "result" in result:
        r = result["result"]
        if "artifacts" in r:
            for a in r["artifacts"]:
                for p in a.get("parts", []):
                    if p.get("type") == "text" or p.get("kind") == "text":
                        return p.get("text", "")
        if "parts" in r:
            for p in r["parts"]:
                if p.get("type") == "text" or p.get("kind") == "text":
                    return p.get("text", "")
    return str(result)


# Create FunctionTool for Router Agent to use
call_data_agent_tool = FunctionTool(func=call_data_agent)
call_support_agent_tool = FunctionTool(func=call_support_agent)

# ============================================================
# Agent 1: Customer Data Agent (Standalone data specialist)
# ============================================================

customer_data_agent = LlmAgent(
    model='gemini-2.0-flash',
    name='customer_data_agent',
    description='Customer database specialist - handles all data queries',
    tools=[mcp_toolset],
    instruction="""You are the Customer Data Agent, a database specialist. You have direct access to the customer database via MCP tools.

Available MCP tools:
- get_customer(customer_id): Get customer details by ID
- list_customers(status, limit): List customers, optionally filter by status
- update_customer(customer_id, data): Update customer information
- create_ticket(customer_id, issue, priority): Create a support ticket
- get_customer_history(customer_id): Get customer's ticket history

Your responsibilities:
1. Fetch customer information accurately
2. Provide customer status, tier, and history
3. Support other agents with data lookups
4. Update customer records when requested

When responding:
- Be precise with data
- Include relevant customer details (ID, name, email, status, tier)
- If a customer is not found, clearly state that
- Provide context that helps other agents make decisions

Example response format:
"Customer #123 (John Doe) is a PREMIUM tier customer, status: active. Email: john@example.com. They have 3 open tickets and have been a customer since January 2024."
"""
)

print("[OK] Customer Data Agent created")

# ============================================================
# Agent 2: Support Agent (Standalone support specialist)
# ============================================================

support_agent = LlmAgent(
    model='gemini-2.0-flash',
    name='support_agent',
    description='Customer support specialist - handles issues, tickets, and escalations',
    tools=[mcp_toolset],
    instruction="""You are the Support Agent, a customer support specialist. You handle customer issues, create tickets, and manage escalations.

Available MCP tools:
- get_customer(customer_id): Get customer details
- create_ticket(customer_id, issue, priority): Create support ticket
- get_customer_history(customer_id): View ticket history
- update_customer(customer_id, data): Update customer info

Your responsibilities:
1. Understand and empathize with customer issues
2. Create tickets with appropriate priority levels:
   - LOW: General inquiries, feedback
   - MEDIUM: Standard issues, questions
   - HIGH: Service disruptions, payment issues
   - URGENT: System outages, security concerns, premium customers with critical issues
3. Check customer history for context
4. Provide helpful, empathetic responses

When responding:
- Acknowledge the customer's issue first
- Explain what action you're taking
- Provide ticket numbers and next steps
- Be warm and professional

For premium/VIP customers: Always use HIGH or URGENT priority.
For billing issues: Always check customer history first.
"""
)

print("[OK] Support Agent created")

# ============================================================
# Agent 3: Router Agent (Intelligent coordinator)
# ============================================================

router_agent = LlmAgent(
    model='gemini-2.0-flash',
    name='router_agent',
    description='Intelligent coordinator that orchestrates between specialist agents',
    tools=[call_data_agent_tool, call_support_agent_tool],
    instruction="""You are the Router Agent, an intelligent coordinator for customer service. You orchestrate between specialist agents to handle complex queries.

Available tools:
- call_data_agent(query): Delegate to Customer Data Agent for database queries
- call_support_agent(query): Delegate to Support Agent for support issues

YOUR WORKFLOW FOR HANDLING REQUESTS:

**Step 1: Analyze the Query**
- Identify what information is needed
- Identify what actions need to be taken
- Determine which agents to involve

**Step 2: Task Allocation**
For simple data queries -> call_data_agent directly
For simple support issues -> call_support_agent directly
For complex queries -> coordinate between agents

**Step 3: Multi-Step Coordination (for complex queries)**
Example workflows:

Scenario A - "Help with account, ID 12345":
1. call_data_agent("Get full customer info for ID 12345 including tier and status")
2. Analyze response to understand customer tier
3. call_support_agent("Handle support for [tier] customer [name]. Context: [data from step 1]")
4. Synthesize responses

Scenario B - "Cancel subscription but having billing issues":
1. call_data_agent("Get customer billing info and history")
2. call_support_agent("Handle cancellation request with billing context: [data from step 1]")
3. Coordinate and synthesize

Scenario C - "Status of high-priority tickets for premium customers":
1. call_data_agent("List all premium/VIP customers")
2. For each premium customer, gather ticket info
3. call_support_agent("Summarize high-priority tickets for these customers: [list]")
4. Synthesize final report

**Step 4: Synthesize and Respond**
- Combine information from all agents
- Provide a coherent, helpful response
- Include relevant details and next steps

IMPORTANT RULES:
1. ALWAYS use the tools to delegate - don't try to answer without consulting specialists
2. For multi-step tasks, call agents in sequence and use each response to inform the next call
3. Pass context between agents - include relevant info from previous responses
4. Your final response should be conversational and synthesize all gathered information
5. When you receive data from Data Agent, pass it to Support Agent if action is needed

Remember: You are the coordinator. Gather information, coordinate specialists, and synthesize the final response.
"""
)

print("[OK] Router Agent created")

# ============================================================
# Agent Cards
# ============================================================

customer_data_agent_card = AgentCard(
    name='Customer Data Agent',
    url=f'http://localhost:{CUSTOMER_DATA_AGENT_PORT}',
    description='Customer database specialist',
    version='2.0',
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=['text/plain'],
    default_output_modes=['text/plain'],
    skills=[
        AgentSkill(
            id='data_ops',
            name='Database Operations',
            description='CRUD operations on customer data',
            tags=['database', 'customer', 'data'],
            examples=["Get customer 1", "List premium customers", "Get customer history"],
        )
    ],
)

support_agent_card = AgentCard(
    name='Support Agent',
    url=f'http://localhost:{SUPPORT_AGENT_PORT}',
    description='Customer support specialist',
    version='2.0',
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=['text/plain'],
    default_output_modes=['text/plain'],
    skills=[
        AgentSkill(
            id='support',
            name='Support Operations',
            description='Handle customer issues and tickets',
            tags=['support', 'tickets', 'help'],
            examples=["Create ticket", "Help with billing", "Handle complaint"],
        )
    ],
)

router_agent_card = AgentCard(
    name='Router Agent',
    url=f'http://localhost:{ROUTER_AGENT_PORT}',
    description='Intelligent service coordinator',
    version='2.0',
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=['text/plain'],
    default_output_modes=['text/plain'],
    skills=[
        AgentSkill(
            id='coordination',
            name='Multi-Agent Coordination',
            description='Orchestrate complex customer service tasks',
            tags=['router', 'coordinator'],
            examples=["I need help with my account", "Complex billing issue"],
        )
    ],
)

# ============================================================
# A2A Server Creation
# ============================================================

def create_a2a_server(agent, agent_card):
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    memory_service = InMemoryMemoryService()

    runner = Runner(
        app_name=agent.name,
        agent=agent,
        session_service=session_service,
        artifact_service=artifact_service,
        memory_service=memory_service,
    )

    config = A2aAgentExecutorConfig()
    executor = A2aAgentExecutor(runner=runner, config=config)

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    return A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )


async def run_server(agent, card, port):
    app = create_a2a_server(agent, card)
    config = uvicorn.Config(app.build(), host='127.0.0.1', port=port, log_level='warning', loop='none')
    await uvicorn.Server(config).serve()


async def start_servers():
    # Start sub-agents first, then Router
    tasks = [
        asyncio.create_task(run_server(customer_data_agent, customer_data_agent_card, CUSTOMER_DATA_AGENT_PORT)),
        asyncio.create_task(run_server(support_agent, support_agent_card, SUPPORT_AGENT_PORT)),
    ]
    await asyncio.sleep(2)  # Wait for sub-agents to start
    
    tasks.append(
        asyncio.create_task(run_server(router_agent, router_agent_card, ROUTER_AGENT_PORT))
    )
    await asyncio.sleep(1)
    
    print('[OK] All servers started!')
    print(f'   Data Agent:    http://127.0.0.1:{CUSTOMER_DATA_AGENT_PORT}')
    print(f'   Support Agent: http://127.0.0.1:{SUPPORT_AGENT_PORT}')
    print(f'   Router Agent:  http://127.0.0.1:{ROUTER_AGENT_PORT}')
    
    await asyncio.gather(*tasks)


def run_in_background():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_servers())


# ============================================================
# Client
# ============================================================

class A2AClient:
    def __init__(self, timeout: float = 120.0):  # Increased timeout for multi-step operations
        self.timeout = timeout

    async def call(self, url: str, message: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            task_id = f"t-{int(time.time()*1000)}"
            payload = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "id": task_id,
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"type": "text", "text": message}],
                        "messageId": task_id,
                    }
                }
            }
            resp = await client.post(url, json=payload)
            result = resp.json()
            
            text_response = extract_text_from_response(result)
            
            return {
                "text": text_response,
                "raw": result
            }


client = A2AClient()

# ============================================================
# Test Scenarios
# ============================================================

async def scenario_1_task_allocation():
    """Scenario 1: Task Allocation - Help a specific customer"""
    tracker.reset()
    
    print(colored("\n" + "=" * 70, "cyan"))
    print(colored("SCENARIO 1: TASK ALLOCATION", "cyan", attrs=["bold"]))
    print(colored("   Query: 'I need help with my account, customer ID 1'", "cyan"))
    print(colored("   Expected: Router -> Data Agent -> Router -> Support Agent -> Response", "cyan"))
    print(colored("=" * 70, "cyan"))
    
    tracker.log("User", "Router Agent", "REQUEST", "I need help with my account, customer ID 1")
    
    start = time.time()
    result = await client.call(
        f'http://localhost:{ROUTER_AGENT_PORT}',
        "I need help with my account, customer ID 1"
    )
    elapsed = time.time() - start
    
    tracker.log("Router Agent", "User", "FINAL_RESPONSE", result["text"])
    
    print(colored(f"\nTotal Time: {elapsed:.2f}s", "white", attrs=["bold"]))
    print(colored("\nFINAL RESPONSE:", "green", attrs=["bold"]))
    print(colored("-" * 50, "white"))
    print(result["text"])
    print(colored("-" * 50, "white"))
    
    tracker.print_summary()
    
    return result


async def scenario_2_negotiation():
    """Scenario 2: Negotiation/Escalation - Multi-intent query"""
    tracker.reset()
    
    print(colored("\n" + "=" * 70, "yellow"))
    print(colored("SCENARIO 2: NEGOTIATION / MULTI-INTENT", "yellow", attrs=["bold"]))
    print(colored("   Query: 'I want to cancel my subscription but I'm having billing issues'", "yellow"))
    print(colored("   Expected: Router analyzes -> Data Agent (billing) -> Support Agent (cancel)", "yellow"))
    print(colored("=" * 70, "yellow"))
    
    tracker.log("User", "Router Agent", "REQUEST", "I want to cancel my subscription but I'm having billing issues")
    
    start = time.time()
    result = await client.call(
        f'http://localhost:{ROUTER_AGENT_PORT}',
        "I want to cancel my subscription but I'm having billing issues. My customer ID is 2."
    )
    elapsed = time.time() - start
    
    tracker.log("Router Agent", "User", "FINAL_RESPONSE", result["text"])
    
    print(colored(f"\nTotal Time: {elapsed:.2f}s", "white", attrs=["bold"]))
    print(colored("\nFINAL RESPONSE:", "green", attrs=["bold"]))
    print(colored("-" * 50, "white"))
    print(result["text"])
    print(colored("-" * 50, "white"))
    
    tracker.print_summary()
    
    return result


async def scenario_3_multi_step():
    """Scenario 3: Multi-Step Coordination - Complex report"""
    tracker.reset()
    
    print(colored("\n" + "=" * 70, "magenta"))
    print(colored("SCENARIO 3: MULTI-STEP COORDINATION", "magenta", attrs=["bold"]))
    print(colored("   Query: 'What is the status of all tickets for active customers?'", "magenta"))
    print(colored("   Expected: Router -> Data Agent (list) -> Support Agent (tickets) -> Report", "magenta"))
    print(colored("=" * 70, "magenta"))
    
    tracker.log("User", "Router Agent", "REQUEST", "What is the status of all tickets for active customers?")
    
    start = time.time()
    result = await client.call(
        f'http://localhost:{ROUTER_AGENT_PORT}',
        "What is the status of all tickets for active customers? Give me a summary report."
    )
    elapsed = time.time() - start
    
    tracker.log("Router Agent", "User", "FINAL_RESPONSE", result["text"])
    
    print(colored(f"\nTotal Time: {elapsed:.2f}s", "white", attrs=["bold"]))
    print(colored("\nFINAL RESPONSE:", "green", attrs=["bold"]))
    print(colored("-" * 50, "white"))
    print(result["text"])
    print(colored("-" * 50, "white"))
    
    tracker.print_summary()
    
    return result


async def custom_query(query: str):
    """Custom query test"""
    tracker.reset()
    
    print(colored("\n" + "=" * 70, "blue"))
    print(colored("CUSTOM QUERY", "blue", attrs=["bold"]))
    print(colored(f"   Query: '{query}'", "blue"))
    print(colored("=" * 70, "blue"))
    
    tracker.log("User", "Router Agent", "REQUEST", query)
    
    start = time.time()
    result = await client.call(f'http://localhost:{ROUTER_AGENT_PORT}', query)
    elapsed = time.time() - start
    
    tracker.log("Router Agent", "User", "FINAL_RESPONSE", result["text"])
    
    print(colored(f"\nTotal Time: {elapsed:.2f}s", "white", attrs=["bold"]))
    print(colored("\nFINAL RESPONSE:", "green", attrs=["bold"]))
    print(colored("-" * 50, "white"))
    print(result["text"])
    print(colored("-" * 50, "white"))
    
    tracker.print_summary()
    
    return result


async def run_all_scenarios():
    """Run all test scenarios"""
    print(colored("\n" + "=" * 70, "white", attrs=["bold"]))
    print(colored("RUNNING ALL A2A COMMUNICATION SCENARIOS", "white", attrs=["bold"]))
    print(colored("=" * 70, "white"))
    
    await scenario_1_task_allocation()
    print("\n" + "-" * 70 + "\n")
    await asyncio.sleep(2)
    
    await scenario_2_negotiation()
    print("\n" + "-" * 70 + "\n")
    await asyncio.sleep(2)
    
    await scenario_3_multi_step()
    
    print(colored("\n" + "=" * 70, "white", attrs=["bold"]))
    print(colored("[OK] ALL SCENARIOS COMPLETED", "green", attrs=["bold"]))
    print(colored("=" * 70, "white"))


# ============================================================
# Direct Tests (Bypass Router)
# ============================================================

async def test_data_agent_direct(query: str):
    """Direct test for Data Agent"""
    tracker.reset()
    print(colored(f"\nDIRECT DATA AGENT TEST: {query}", "cyan", attrs=["bold"]))
    
    tracker.log("User", "Data Agent", "DIRECT_REQUEST", query)
    result = await client.call(f'http://localhost:{CUSTOMER_DATA_AGENT_PORT}', query)
    tracker.log("Data Agent", "User", "RESPONSE", result["text"])
    
    print(colored("\nResponse:", "green"))
    print(result["text"])
    return result


async def test_support_agent_direct(query: str):
    """Direct test for Support Agent"""
    tracker.reset()
    print(colored(f"\nDIRECT SUPPORT AGENT TEST: {query}", "yellow", attrs=["bold"]))
    
    tracker.log("User", "Support Agent", "DIRECT_REQUEST", query)
    result = await client.call(f'http://localhost:{SUPPORT_AGENT_PORT}', query)
    tracker.log("Support Agent", "User", "RESPONSE", result["text"])
    
    print(colored("\nResponse:", "green"))
    print(result["text"])
    return result


# ============================================================
# Main Entry Point
# ============================================================

if __name__ == "__main__":
    print(colored("\n" + "=" * 70, "white", attrs=["bold"]))
    print(colored("A2A MULTI-AGENT CUSTOMER SERVICE SYSTEM - ADVANCED", "white", attrs=["bold"]))
    print(colored("=" * 70, "white"))
    print("\n[WARNING] Make sure MCP Server is running on port 5000!")
    print("    Run: python mcp_server.py")
    
    # Start servers
    print("\n[INFO] Starting A2A servers...")
    threading.Thread(target=run_in_background, daemon=True).start()
    time.sleep(5)  # Wait for all servers to start
    
    # Run all scenarios
    asyncio.run(run_all_scenarios())