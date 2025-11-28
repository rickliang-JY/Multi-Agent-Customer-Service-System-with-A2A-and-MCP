"""
Customer Data Agent - A2A Server
Independent A2A service for customer data operations
Uses MCP Server for database operations.
"""

import json
import re
import httpx
import asyncio
import sys

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard,
    AgentSkill,
    AgentCapabilities,
    Part,
    TextPart,
)
from a2a.utils import new_task


class MCPClient:
    """HTTP client for MCP Server"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    async def call_tool(self, name, arguments):
        """Call MCP tool via HTTP"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tools/call",
                    json={
                        "jsonrpc": "2.0",
                        "id": "1",
                        "method": "tools/call",
                        "params": {"name": name, "arguments": arguments}
                    }
                )
                result = response.json()
                
                if "result" in result and "content" in result["result"]:
                    text = result["result"]["content"][0]["text"]
                    return json.loads(text)
                return result
            except Exception as e:
                return {"success": False, "error": str(e)}


# Global MCP client
mcp_client = MCPClient()


class CustomerDataAgentExecutor(AgentExecutor):
    """Processes customer data requests using MCP tools."""
    
    def __init__(self, mcp_url="http://localhost:8000"):
        global mcp_client
        mcp_client = MCPClient(mcp_url)
    
    async def execute(self, context, event_queue):
        """Handle A2A request"""
        query = context.get_user_input()
        
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
        
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        
        try:
            result = await self._process_query(query)
            response = json.dumps(result, indent=2, default=str)
            
            text_part = Part(root=TextPart(text=response))
            await updater.add_artifact(parts=[text_part])
            await updater.complete()
            
        except Exception as e:
            error_part = Part(root=TextPart(text=f"Error: {str(e)}"))
            try:
                await updater.add_artifact(parts=[error_part])
                await updater.fail()
            except:
                pass

    async def cancel(self, context, event_queue):
        pass
    
    async def _process_query(self, query):
        """Process query and call appropriate MCP tools"""
        query_lower = query.lower()
        results = []
        
        # Extract customer ID
        customer_id = None
        patterns = [r"customer\s*(?:id\s*)?\s*(\d+)", r"id\s+(\d+)", r"#(\d+)"]
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                customer_id = int(match.group(1))
                break
        
        # Determine operation and execute
        if "update" in query_lower and customer_id:
            update_data = {}
            email_match = re.search(r'email\s*(?:to\s*)?(\S+@\S+)', query_lower)
            if email_match:
                update_data["email"] = email_match.group(1)
            
            if "disable" in query_lower:
                update_data["status"] = "disabled"
            elif "activate" in query_lower:
                update_data["status"] = "active"
            
            if update_data:
                result = await mcp_client.call_tool("update_customer", {
                    "customer_id": customer_id, "data": update_data
                })
                results.append({"tool": "update_customer", "result": result})
        
        elif "list" in query_lower and "customer" in query_lower:
            args = {"limit": 20}
            if "active" in query_lower:
                args["status"] = "active"
            elif "disabled" in query_lower:
                args["status"] = "disabled"
            result = await mcp_client.call_tool("list_customers", args)
            results.append({"tool": "list_customers", "result": result})
        
        elif "priority" in query_lower and "ticket" in query_lower:
            priority = "high"
            if "medium" in query_lower:
                priority = "medium"
            elif "low" in query_lower:
                priority = "low"
            args = {"priority": priority}
            if "open" in query_lower:
                args["status"] = "open"
            result = await mcp_client.call_tool("get_tickets_by_priority", args)
            results.append({"tool": "get_tickets_by_priority", "result": result})
        
        elif "history" in query_lower and customer_id:
            result = await mcp_client.call_tool("get_customer_history", {"customer_id": customer_id})
            results.append({"tool": "get_customer_history", "result": result})
        
        elif customer_id:
            result = await mcp_client.call_tool("get_customer", {"customer_id": customer_id})
            results.append({"tool": "get_customer", "result": result})
        
        return {"agent": "CustomerDataAgent", "operations": results}


def create_agent_card(host, port):
    """Create the A2A Agent Card"""
    skills = [
        AgentSkill(id="get_customer", name="Get Customer",
                   description="Retrieve customer information by ID",
                   tags=["customer", "data"], examples=["Get customer 5"]),
        AgentSkill(id="update_customer", name="Update Customer",
                   description="Update customer information",
                   tags=["customer", "update"], examples=["Update customer 7 email"]),
        AgentSkill(id="list_customers", name="List Customers",
                   description="List customers with optional filter",
                   tags=["customer", "list"], examples=["List active customers"]),
        AgentSkill(id="get_customer_history", name="Get Customer History",
                   description="Get customer ticket history",
                   tags=["customer", "tickets"], examples=["Show history for customer 5"]),
        AgentSkill(id="get_tickets_by_priority", name="Get Tickets by Priority",
                   description="Get tickets by priority level",
                   tags=["tickets", "priority"], examples=["Get high priority tickets"]),
    ]
    
    return AgentCard(
        name="Customer Data Agent",
        description="Agent for customer data operations via MCP tools",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=skills,
    )


def run_server(host="localhost", port=8001, mcp_url="http://localhost:8000"):
    """Run the Customer Data Agent A2A Server"""
    agent_executor = CustomerDataAgentExecutor(mcp_url)
    agent_card = create_agent_card(host, port)
    
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=InMemoryTaskStore()
    )
    
    a2a_app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )
    
    print("=" * 60)
    print("Customer Data Agent - A2A Server")
    print("=" * 60)
    print(f"Agent Card: http://{host}:{port}/.well-known/agent.json")
    print(f"MCP Server: {mcp_url}")
    print("=" * 60)
    
    uvicorn.run(a2a_app.build(), host=host, port=port)


if __name__ == "__main__":
    port = 8001
    mcp_url = "http://localhost:8000"
    
    # Parse command line args
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
        if arg == "--mcp-url" and i + 1 < len(sys.argv):
            mcp_url = sys.argv[i + 1]
    
    run_server(port=port, mcp_url=mcp_url)
