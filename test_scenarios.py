"""
Test Scenarios for A2A Multi-Agent Customer Service System
Tests the three required scenarios: Task Allocation, Negotiation, Multi-step

Run with: python test_scenarios.py
Requires all servers to be running (use run_servers.py first)
"""

import asyncio
import httpx
import json
import uuid
import textwrap
from datetime import datetime

# Configuration
MCP_SERVER_URL = "http://localhost:8000"
CUSTOMER_DATA_AGENT_URL = "http://localhost:8001"
SUPPORT_AGENT_URL = "http://localhost:8002"

# ============================================================================
# Output Formatting Utilities
# ============================================================================

def print_separator(title="", char="="):
    print("\n" + char * 70)
    if title:
        print(f"  {title}")
        print(char * 70)

def print_json(data, indent=2, prefix="    "):
    """Pretty print JSON data with prefix"""
    formatted = json.dumps(data, indent=indent, default=str)
    for line in formatted.split('\n'):
        print(f"{prefix}{line}")

def print_wrapped_text(text, width=66, prefix="    | "):
    """Print text with word wrapping"""
    lines = text.split('\n')
    for line in lines:
        if line.strip():
            wrapped = textwrap.wrap(line, width=width)
            for wrapped_line in wrapped:
                print(f"{prefix}{wrapped_line}")
        else:
            print(f"{prefix}")

def print_box(title, content, width=68):
    """Print content in a nice box"""
    print(f"\n    +{'-' * width}+")
    print(f"    | {title.ljust(width - 2)} |")
    print(f"    +{'-' * width}+")
    
    if isinstance(content, list):
        for line in content:
            print(f"    | {line.ljust(width - 2)} |")
    else:
        print_wrapped_text(content, width=width-4, prefix="    | ")
    
    print(f"    +{'-' * width}+")

def format_support_response(response_data):
    """Format Support Agent response nicely"""
    if not response_data:
        return
    
    print("\n    " + "=" * 60)
    print("    SUPPORT AGENT RESPONSE")
    print("    " + "=" * 60)
    
    if isinstance(response_data, dict):
        # Extract agent info
        agent = response_data.get("agent", "Support Agent")
        response_text = response_data.get("response", "")
        
        print(f"\n    Agent: {agent}")
        print("    " + "-" * 60)
        
        if response_text:
            print("\n    Response Content:")
            print("    " + "-" * 60)
            print_wrapped_text(response_text, width=56, prefix="    | ")
            print("    " + "-" * 60)
    else:
        print(f"\n    {response_data}")
    
    print("    " + "=" * 60)

def format_customer_data_response(response_data):
    """Format Customer Data Agent response nicely"""
    if not response_data:
        return
    
    print("\n    " + "=" * 60)
    print("    CUSTOMER DATA AGENT RESPONSE")
    print("    " + "=" * 60)
    
    if isinstance(response_data, dict):
        agent = response_data.get("agent", "Customer Data Agent")
        operations = response_data.get("operations", [])
        
        print(f"\n    Agent: {agent}")
        print(f"    Operations: {len(operations)}")
        print("    " + "-" * 60)
        
        for i, op in enumerate(operations):
            tool = op.get("tool", "unknown")
            result = op.get("result", {})
            
            print(f"\n    Operation {i+1}: {tool}")
            print("    " + "-" * 40)
            
            if result.get("success"):
                data = result.get("data")
                if isinstance(data, list):
                    print(f"    Records found: {len(data)}")
                    for item in data[:5]:  # Show first 5
                        if item.get("name"):
                            email_or_status = item.get('email', item.get('status', ''))
                            print(f"      - ID {item.get('id')}: {item.get('name')} ({email_or_status})")
                        elif item.get("subject"):
                            subject = item.get('subject', 'No subject')
                            subject = subject[:40] if subject else 'No subject'
                            priority = item.get('priority', 'N/A')
                            print(f"      - Ticket {item.get('id')}: {subject} [{priority}]")
                        else:
                            print(f"      - {item}")
                    if len(data) > 5:
                        print(f"      ... and {len(data) - 5} more")
                elif isinstance(data, dict):
                    if data.get("name"):
                        print(f"    Customer: {data.get('name')}")
                        print(f"    Email: {data.get('email', 'N/A')}")
                        print(f"    Status: {data.get('status', 'N/A')}")
                    if data.get("tickets"):
                        tickets = data.get("tickets", [])
                        print(f"    Tickets: {len(tickets)}")
                        for t in tickets[:3]:
                            subject = t.get('subject', 'No subject')
                            subject = subject[:35] if subject else 'No subject'
                            priority = t.get('priority', 'N/A')
                            print(f"      - {subject} [{priority}]")
                    elif not data.get("name"):
                        # Generic dict display
                        for key, value in list(data.items())[:5]:
                            print(f"    {key}: {value}")
            else:
                print(f"    Error: {result.get('error', 'Unknown error')}")
    
    print("\n    " + "=" * 60)

# ============================================================================
# Server Health Check
# ============================================================================

async def check_servers():
    """Check if all servers are running"""
    print_separator("Server Health Check")
    
    servers = [
        ("MCP Server", MCP_SERVER_URL, "/health"),
        ("Customer Data Agent", CUSTOMER_DATA_AGENT_URL, "/.well-known/agent-card.json"),
        ("Support Agent", SUPPORT_AGENT_URL, "/.well-known/agent-card.json"),
    ]
    
    all_ok = True
    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, url, endpoint in servers:
            try:
                r = await client.get(f"{url}{endpoint}")
                if r.status_code == 200:
                    print(f"  [OK] {name}: {url}")
                else:
                    print(f"  [FAIL] {name}: Status {r.status_code}")
                    all_ok = False
            except Exception as e:
                print(f"  [FAIL] {name}: {e}")
                all_ok = False
    
    return all_ok


# ============================================================================
# MCP Server Tests
# ============================================================================

async def test_mcp_server():
    """Test MCP Server endpoints"""
    print_separator("TEST: MCP Server")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test tools/list
        print("\n>>> Request: POST /tools/list")
        r = await client.post(f"{MCP_SERVER_URL}/tools/list", json={
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/list"
        })
        data = r.json()
        print("<<< Response:")
        tools = data.get("result", {}).get("tools", [])
        print(f"    Found {len(tools)} tools:")
        for tool in tools:
            print(f"      - {tool['name']}: {tool.get('description', '')[:50]}...")
        
        # Test tools/call - get_customer
        print("\n>>> Request: POST /tools/call (get_customer)")
        print("    Params: {customer_id: 1}")
        r = await client.post(f"{MCP_SERVER_URL}/tools/call", json={
            "jsonrpc": "2.0",
            "id": "2",
            "method": "tools/call",
            "params": {
                "name": "get_customer",
                "arguments": {"customer_id": 1}
            }
        })
        data = r.json()
        print("<<< Response:")
        if "result" in data:
            content = json.loads(data["result"]["content"][0]["text"])
            print_json(content)
        
        # Test tools/call - get_tickets_by_priority
        print("\n>>> Request: POST /tools/call (get_tickets_by_priority)")
        print("    Params: {priority: 'high'}")
        r = await client.post(f"{MCP_SERVER_URL}/tools/call", json={
            "jsonrpc": "2.0",
            "id": "4",
            "method": "tools/call",
            "params": {
                "name": "get_tickets_by_priority",
                "arguments": {"priority": "high"}
            }
        })
        data = r.json()
        print("<<< Response:")
        if "result" in data:
            content = json.loads(data["result"]["content"][0]["text"])
            print(f"    Found {len(content.get('data', []))} high priority tickets")


# ============================================================================
# A2A Message Helper
# ============================================================================

async def send_a2a_message(client, url, message, agent_name, format_response=True):
    """Send A2A message and return response"""
    message_id = str(uuid.uuid4())
    
    print(f"\n>>> A2A Request to {agent_name}")
    print(f"    URL: {url}")
    msg_display = message[:80] + "..." if len(message) > 80 else message
    print(f"    Message: \"{msg_display}\"")
    
    request_body = {
        "jsonrpc": "2.0",
        "id": datetime.now().isoformat(),
        "method": "message/send",
        "params": {
            "message": {
                "messageId": message_id,
                "role": "user",
                "parts": [{"kind": "text", "text": message}]
            }
        }
    }
    
    r = await client.post(url, json=request_body)
    data = r.json()
    
    print(f"\n<<< A2A Response from {agent_name}")
    
    if "error" in data:
        print(f"    ERROR: {data['error']}")
        return None, None
    
    parsed_content = None
    
    if "result" in data:
        result = data["result"]
        status = result.get("status", {})
        print(f"    Task ID: {result.get('id', 'N/A')}")
        print(f"    Status: {status.get('state', 'N/A')}")
        
        if "artifacts" in result:
            for artifact in result["artifacts"]:
                for part in artifact.get("parts", []):
                    if part.get("kind") == "text":
                        text = part.get("text", "")
                        try:
                            parsed_content = json.loads(text)
                        except:
                            parsed_content = text
        
        # Format response based on agent type
        if format_response and parsed_content:
            if "Support" in agent_name:
                format_support_response(parsed_content)
            else:
                format_customer_data_response(parsed_content)
        
        return result, parsed_content
    
    return None, None


# ============================================================================
# A2A Agent Tests
# ============================================================================

async def test_customer_data_agent():
    """Test Customer Data Agent A2A endpoints"""
    print_separator("TEST: Customer Data Agent (A2A)")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Test Agent Card
        print("\n>>> Request: GET /.well-known/agent-card.json")
        r = await client.get(f"{CUSTOMER_DATA_AGENT_URL}/.well-known/agent-card.json")
        card = r.json()
        print("<<< Response:")
        print(f"    Name: {card.get('name')}")
        print(f"    Description: {card.get('description')}")
        print(f"    Skills: {[s.get('id') for s in card.get('skills', [])]}")
        
        # Test message/send - Get customer
        await send_a2a_message(
            client, 
            CUSTOMER_DATA_AGENT_URL, 
            "Get customer 5 information",
            "Customer Data Agent"
        )
        
        # Test message/send - Get tickets
        await send_a2a_message(
            client,
            CUSTOMER_DATA_AGENT_URL,
            "Show high priority tickets",
            "Customer Data Agent"
        )


async def test_support_agent():
    """Test Support Agent A2A endpoints"""
    print_separator("TEST: Support Agent (A2A)")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Test Agent Card
        print("\n>>> Request: GET /.well-known/agent-card.json")
        r = await client.get(f"{SUPPORT_AGENT_URL}/.well-known/agent-card.json")
        card = r.json()
        print("<<< Response:")
        print(f"    Name: {card.get('name')}")
        print(f"    Description: {card.get('description')}")
        print(f"    Skills: {[s.get('id') for s in card.get('skills', [])]}")
        
        # Test message/send - Simple query
        await send_a2a_message(
            client,
            SUPPORT_AGENT_URL,
            "Hello, I need help with my account",
            "Support Agent"
        )


# ============================================================================
# Import Orchestrator
# ============================================================================

from orchestrator import Orchestrator

# ============================================================================
# Scenario 1: Simple Query
# ============================================================================

async def test_scenario_simple_query():
    """Scenario 1: Simple Query - Single agent, straightforward MCP call"""
    print_separator("SCENARIO 1: Simple Query")
    print("  Query: \"Get customer information for ID 5\"")
    print("  Expected: Single agent (Customer Data), straightforward MCP call")
    
    orchestrator = Orchestrator(verbose=True)
    await orchestrator.initialize()
    
    await orchestrator.process_query("Get customer information for ID 5")


# ============================================================================
# Scenario 2: Coordinated Query
# ============================================================================

async def test_scenario_coordinated_query():
    """Scenario 2: Coordinated Query - Multiple agents coordinate"""
    print_separator("SCENARIO 2: Coordinated Query")
    print("  Query: \"I'm customer 5 and need help upgrading my account\"")
    print("  Expected: Multiple agents coordinate (data fetch + support response)")
    
    orchestrator = Orchestrator(verbose=True)
    await orchestrator.initialize()
    
    await orchestrator.process_query("I'm customer 5 and need help upgrading my account")


# ============================================================================
# Scenario 3: Complex Query
# ============================================================================

async def test_scenario_complex_query():
    """Scenario 3: Complex Query - Negotiation between agents"""
    print_separator("SCENARIO 3: Complex Query")
    print("  Query: \"Show me all active customers who have open tickets\"")
    print("  Expected: Negotiation between data and support agents")
    
    orchestrator = Orchestrator(verbose=True)
    await orchestrator.initialize()
    
    await orchestrator.process_query("Show me all active customers who have open tickets")


# ============================================================================
# Scenario 4: Escalation
# ============================================================================

async def test_scenario_escalation():
    """Scenario 4: Escalation - Identify urgency and route appropriately"""
    print_separator("SCENARIO 4: Escalation")
    print("  Query: \"I've been charged twice, please refund immediately!\"")
    print("  Expected: Router identifies urgency, routes with HIGH priority")
    
    orchestrator = Orchestrator(verbose=True)
    await orchestrator.initialize()
    
    await orchestrator.process_query("I've been charged twice, please refund immediately!")


# ============================================================================
# Scenario 5: Multi-Intent
# ============================================================================

async def test_scenario_multi_intent():
    """Scenario 5: Multi-Intent - Parallel task execution and coordination"""
    print_separator("SCENARIO 5: Multi-Intent")
    print("  Query: \"Update my email to new@email.com and show my ticket history\"")
    print("  Expected: Parallel task execution (update + fetch)")
    
    orchestrator = Orchestrator(verbose=True)
    await orchestrator.initialize()
    
    await orchestrator.process_query("Update my email to new@email.com and show my ticket history for customer 3")



# ============================================================================
# Main
# ============================================================================

async def main():
    """Run all tests"""
    print("\n")
    print("=" * 70)
    print("  A2A MULTI-AGENT CUSTOMER SERVICE SYSTEM - TEST SUITE")
    print("=" * 70)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Check servers
    if not await check_servers():
        print("\n[ERROR] Not all servers are running!")
        print("Please start servers first: python run_servers.py")
        return
    
    # Run tests
    await test_mcp_server()
    await test_customer_data_agent()
    await test_support_agent()
    
    # Run scenarios
    await test_scenario_simple_query()
    await test_scenario_coordinated_query()
    await test_scenario_complex_query()
    await test_scenario_escalation()
    await test_scenario_multi_intent()
    



if __name__ == "__main__":
    asyncio.run(main())