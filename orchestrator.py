"""
A2A Orchestrator - Multi-Agent Coordinator
Real orchestrator that coordinates between Customer Data Agent and Support Agent

This orchestrator:
1. Receives user queries
2. Analyzes and decomposes queries into sub-tasks
3. Routes tasks to appropriate agents via A2A protocol
4. Aggregates results and returns final response

Demonstrates:
- Task Allocation: Route queries to correct agent
- Negotiation: Pass data between agents
- Multi-step: Execute dependent tasks in sequence
"""

import json
import asyncio
import uuid
import re
import textwrap
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

import httpx

# ============================================================================
# Configuration
# ============================================================================

AGENT_URLS = {
    "customer_data": "http://localhost:8001",
    "support": "http://localhost:8002"
}

# ============================================================================
# Data Models
# ============================================================================

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class SubTask:
    id: str
    description: str
    agent: str
    query: str
    depends_on: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None

@dataclass
class OrchestrationResult:
    query: str
    sub_tasks: List[SubTask]
    final_response: str
    success: bool

# ============================================================================
# A2A Client
# ============================================================================

class A2AClient:
    """Client for communicating with A2A agents"""
    
    def __init__(self, agent_url: str, agent_name: str):
        self.agent_url = agent_url.rstrip('/')
        self.agent_name = agent_name
        self.agent_card = None
    
    async def get_agent_card(self) -> Dict:
        """Fetch the agent's Agent Card"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.agent_url}/.well-known/agent-card.json"
            )
            self.agent_card = response.json()
            return self.agent_card
    
    async def send_message(self, message: str, context_id: str = None) -> Dict:
        """Send a message to the agent via A2A protocol"""
        message_id = str(uuid.uuid4())
        
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
        
        if context_id:
            request_body["params"]["message"]["contextId"] = context_id
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.agent_url, json=request_body)
            return response.json()

# ============================================================================
# Orchestrator
# ============================================================================

class Orchestrator:
    """
    Multi-Agent Orchestrator
    Coordinates between agents using A2A protocol
    """
    
    def __init__(self, verbose: bool = True):
        self.clients = {
            name: A2AClient(url, name) 
            for name, url in AGENT_URLS.items()
        }
        self.verbose = verbose
        self.task_results: Dict[str, Any] = {}
    
    def log(self, message: str, level: str = "info"):
        """Log orchestrator activity"""
        if self.verbose:
            print(message)
    
    def log_step(self, step_num: int, message: str):
        """Log a numbered step"""
        if self.verbose:
            print(f"   {step_num}. {message}")
    
    async def initialize(self):
        """Initialize by fetching agent cards"""
        for name, client in self.clients.items():
            try:
                card = await client.get_agent_card()
                client.agent_card = card
            except Exception as e:
                if self.verbose:
                    print(f"  Failed to connect to {name}: {e}")
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze query to determine routing and task decomposition"""
        query_lower = query.lower()
        
        analysis = {
            "customer_id": None,
            "needs_customer_data": False,
            "needs_tickets": False,
            "needs_support_response": False,
            "needs_billing": False,
            "needs_update": False,
            "update_data": {},
            "has_multiple_intents": False,
            "is_urgent": False,
            "intents": [],
            "operation_type": "unknown",
            "keywords": []
        }
        
        # Extract customer ID
        for pattern in [r"customer\s*(?:id\s*)?\s*(\d+)", r"id\s+(\d+)", r"#(\d+)", r"i'm customer\s*(\d+)", r"customer\s*(\d+)"]:
            match = re.search(pattern, query_lower)
            if match:
                analysis["customer_id"] = int(match.group(1))
                break
        
        # Extract email for update
        email_match = re.search(r"email\s+(?:to\s+)?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", query_lower)
        if email_match:
            analysis["update_data"]["email"] = email_match.group(1)
            analysis["needs_update"] = True
            analysis["intents"].append("update")
        
        # Detect urgency/escalation
        if any(kw in query_lower for kw in ["immediately", "urgent", "asap", "right now", "charged twice", "refund", "emergency"]):
            analysis["is_urgent"] = True
            analysis["intents"].append("escalation")
            analysis["needs_support_response"] = True
            analysis["needs_customer_data"] = True
        
        # Detect intents
        if any(kw in query_lower for kw in ["cancel", "cancellation", "unsubscribe", "stop"]):
            analysis["intents"].append("cancellation")
        
        if any(kw in query_lower for kw in ["billing", "bill", "charge", "payment", "invoice", "refund"]):
            analysis["intents"].append("billing")
            analysis["needs_billing"] = True
            analysis["needs_customer_data"] = True
        
        if any(kw in query_lower for kw in ["upgrade", "downgrade", "change plan", "switch plan"]):
            analysis["intents"].append("plan_change")
            analysis["needs_customer_data"] = True
            analysis["needs_support_response"] = True
        
        if any(kw in query_lower for kw in ["customer", "list", "show", "get", "information", "active"]):
            analysis["needs_customer_data"] = True
            analysis["keywords"].append("customer_data")
        
        if any(kw in query_lower for kw in ["ticket", "priority", "issue", "problem", "open ticket", "history"]):
            analysis["needs_tickets"] = True
            analysis["keywords"].append("tickets")
        
        if any(kw in query_lower for kw in ["help", "summary", "summarize", "explain", "understand", "analyze", "policy", "how to", "need help"]):
            analysis["needs_support_response"] = True
            analysis["keywords"].append("support")
        
        # Determine operation type
        if analysis["is_urgent"]:
            analysis["operation_type"] = "escalation"
        elif analysis["needs_update"] and (analysis["needs_tickets"] or analysis["needs_customer_data"]):
            analysis["operation_type"] = "multi_intent"
            analysis["has_multiple_intents"] = True
        elif len(analysis["intents"]) >= 2:
            analysis["has_multiple_intents"] = True
            analysis["needs_support_response"] = True
            analysis["operation_type"] = "negotiation"
        elif analysis["needs_customer_data"] and analysis["needs_tickets"]:
            # Complex query: needs both customer data AND ticket data
            analysis["operation_type"] = "negotiation"
            analysis["has_multiple_intents"] = True
        elif analysis["needs_support_response"] and (analysis["needs_customer_data"] or analysis["needs_tickets"]):
            analysis["operation_type"] = "coordinated"
        elif analysis["needs_support_response"]:
            analysis["operation_type"] = "support_only"
        else:
            analysis["operation_type"] = "simple"
        
        return analysis
    
    def create_sub_tasks(self, query: str, analysis: Dict) -> List[SubTask]:
        """Create sub-tasks based on query analysis"""
        tasks = []
        task_num = 0
        query_lower = query.lower()
        
        if analysis["needs_customer_data"] or analysis["needs_tickets"]:
            task_num += 1
            
            # Determine the data query
            if analysis["needs_tickets"] and "priority" in query_lower:
                data_query = "Get all high priority tickets"
            elif analysis["needs_tickets"] and "open" in query_lower:
                data_query = "Get all open tickets"
            elif analysis["customer_id"]:
                data_query = f"Get customer {analysis['customer_id']} information and history"
            elif analysis["needs_tickets"]:
                data_query = "Get tickets by priority"
            else:
                data_query = "List customers"
            
            tasks.append(SubTask(
                id=f"task_{task_num}",
                description="Retrieve data from Customer Data Agent",
                agent="customer_data",
                query=data_query,
                depends_on=[]
            ))
        
        if analysis["needs_support_response"]:
            task_num += 1
            depends = [t.id for t in tasks]  # Depends on all previous tasks
            
            tasks.append(SubTask(
                id=f"task_{task_num}",
                description="Generate response via Support Agent",
                agent="support",
                query=query,  # Will be enriched with context
                depends_on=depends
            ))
        
        # If no tasks created, default to customer data
        if not tasks:
            tasks.append(SubTask(
                id="task_1",
                description="Process query via Customer Data Agent",
                agent="customer_data",
                query=query,
                depends_on=[]
            ))
        
        return tasks
    
    async def execute_task(self, task: SubTask, silent: bool = False) -> Dict[str, Any]:
        """Execute a single sub-task"""
        client = self.clients.get(task.agent)
        if not client:
            return {"success": False, "error": f"Unknown agent: {task.agent}"}
        
        # Build query with context from dependencies
        query = task.query
        if task.depends_on:
            context_data = {
                dep_id: self.task_results.get(dep_id, {})
                for dep_id in task.depends_on
            }
            query = f"{task.query}\n\nContext from previous steps: {json.dumps(context_data, default=str)}"
        
        # Send A2A message
        response = await client.send_message(query)
        
        # Extract result
        result = {"success": False, "raw": response}
        
        if "result" in response:
            result["success"] = True
            result["task_id"] = response["result"].get("id")
            result["status"] = response["result"].get("status", {}).get("state")
            
            # Extract artifact content
            if "artifacts" in response["result"]:
                for artifact in response["result"]["artifacts"]:
                    for part in artifact.get("parts", []):
                        if part.get("kind") == "text":
                            try:
                                result["content"] = json.loads(part["text"])
                            except:
                                result["content"] = part["text"]
        
        return result
    
    async def process_query(self, query: str) -> OrchestrationResult:
        """
        Main orchestration method
        Processes a query through the multi-agent system
        """
        # Analyze query
        analysis = self.analyze_query(query)
        
        # Print A2A Flow header
        if self.verbose:
            print("\n  A2A Flow:")
        
        step_num = 1
        
        # Different flows based on operation type
        if analysis["operation_type"] == "escalation":
            return await self._process_escalation(query, analysis, step_num)
        elif analysis["operation_type"] == "multi_intent":
            return await self._process_multi_intent(query, analysis, step_num)
        elif analysis["operation_type"] == "negotiation":
            return await self._process_negotiation(query, analysis, step_num)
        elif analysis["operation_type"] == "coordinated":
            return await self._process_coordinated(query, analysis, step_num)
        else:
            return await self._process_simple(query, analysis, step_num)
    
    async def _process_negotiation(self, query: str, analysis: Dict, step_num: int) -> OrchestrationResult:
        """Handle negotiation scenario with multiple intents"""
        tools_used = []
        sub_tasks = []
        self.task_results = {}
        
        # Step 1: Router detects multiple intents
        intents_str = " + ".join(analysis["intents"])
        self.log_step(step_num, f"Router detects multiple intents ({intents_str})")
        step_num += 1
        
        # Step 2: Router -> Support Agent: "Can you handle this?"
        self.log_step(step_num, f"Router Agent -> Support Agent: \"Can you handle: {query[:40]}...?\"")
        step_num += 1
        
        # Step 3: Support Agent -> Router: "I need context"
        self.log_step(step_num, f"Support Agent -> Router Agent: \"I need billing/customer context first\"")
        step_num += 1
        
        # Step 4: Router -> Customer Data Agent: Get context
        data_query = "Get customer billing and account information"
        if analysis["customer_id"]:
            data_query = f"Get customer {analysis['customer_id']} billing and account information"
        else:
            data_query = "List customers with their billing status"
        
        self.log_step(step_num, f"Router Agent -> Customer Data Agent: \"{data_query[:45]}\"")
        step_num += 1
        
        # Execute Customer Data Agent task
        task1 = SubTask(
            id="task_1",
            description="Get customer context",
            agent="customer_data",
            query=data_query,
            depends_on=[]
        )
        sub_tasks.append(task1)
        
        result1 = await self.execute_task(task1, silent=True)
        
        if result1.get("success"):
            task1.status = TaskStatus.COMPLETED
            task1.result = result1
            self.task_results["task_1"] = result1.get("content", {})
            
            # Extract tool info
            content = result1.get("content", {})
            if isinstance(content, dict) and content.get("operations"):
                for op in content.get("operations", []):
                    tool = op.get("tool", "unknown")
                    tools_used.append(tool)
                    op_result = op.get("result", {})
                    if op_result.get("success"):
                        data = op_result.get("data")
                        if isinstance(data, list):
                            self.log_step(step_num, f"Customer Data Agent -> Router Agent: Returns {len(data)} records (via MCP: {tool})")
                        elif isinstance(data, dict):
                            name = data.get("customer", {}).get("name") if data.get("customer") else data.get("name", "data")
                            self.log_step(step_num, f"Customer Data Agent -> Router Agent: Returns context for \"{name}\" (via MCP: {tool})")
                        step_num += 1
        else:
            task1.status = TaskStatus.FAILED
            self.log_step(step_num, "Customer Data Agent -> Router Agent: FAILED")
            step_num += 1
        
        # Step 5: Router negotiates - sends context to Support Agent
        self.log_step(step_num, "Router Agent negotiates between agents to formulate response")
        step_num += 1
        
        # Send to Support Agent with context
        support_query = f"Customer wants to cancel subscription due to billing issues. Please help resolve. Query: {query}"
        
        self.log_step(step_num, f"Router Agent -> Support Agent: \"Handle with context from Customer Data\"")
        step_num += 1
        
        task2 = SubTask(
            id="task_2",
            description="Generate coordinated response",
            agent="support",
            query=support_query,
            depends_on=["task_1"]
        )
        sub_tasks.append(task2)
        
        result2 = await self.execute_task(task2, silent=True)
        
        if result2.get("success"):
            task2.status = TaskStatus.COMPLETED
            task2.result = result2
            self.task_results["task_2"] = result2.get("content", {})
            
            content = result2.get("content", {})
            if isinstance(content, dict) and content.get("response"):
                response_len = len(content.get("response", ""))
                self.log_step(step_num, f"Support Agent -> Router Agent: Generates coordinated response ({response_len} chars)")
                step_num += 1
        else:
            task2.status = TaskStatus.FAILED
            self.log_step(step_num, "Support Agent -> Router Agent: FAILED")
            step_num += 1
        
        # Final step
        self.log_step(step_num, "Router Agent sends coordinated response to customer")
        
        # Get final response
        final_task = sub_tasks[-1]
        final_response = ""
        
        if final_task.result and final_task.result.get("content"):
            content = final_task.result["content"]
            if isinstance(content, dict):
                if content.get("response"):
                    final_response = content["response"]
                else:
                    final_response = json.dumps(content, indent=2, default=str)
            else:
                final_response = str(content)
        
        # Print summary
        if self.verbose:
            print(f"\n  Summary:")
            print(f"   - Scenario: Negotiation (multiple intents: {intents_str})")
            print(f"   - Agents used: customer_data, support")
            if tools_used:
                print(f"   - MCP Tools called: {', '.join(tools_used)}")
            print(f"   - Status: {'SUCCESS' if all(t.status == TaskStatus.COMPLETED for t in sub_tasks) else 'FAILED'}")
        
        # Print final response
        if self.verbose and final_task.result and final_task.result.get("content"):
            self._print_structured_response(final_task.result["content"])
        
        return OrchestrationResult(
            query=query,
            sub_tasks=sub_tasks,
            final_response=final_response,
            success=all(t.status == TaskStatus.COMPLETED for t in sub_tasks)
        )
    
    async def _process_simple(self, query: str, analysis: Dict, step_num: int) -> OrchestrationResult:
        """Scenario 1: Simple Query - Single agent, straightforward MCP call"""
        sub_tasks = []
        tools_used = []
        self.task_results = {}
        
        # Step 1: Router receives query
        self.log_step(step_num, f"Router Agent receives query: \"{query[:50]}{'...' if len(query) > 50 else ''}\"")
        step_num += 1
        
        # Determine data query
        if analysis["customer_id"]:
            data_query = f"Get customer {analysis['customer_id']} information"
        elif analysis["needs_tickets"]:
            data_query = "Get tickets"
        else:
            data_query = "List customers"
        
        # Step 2: Router -> Customer Data Agent
        self.log_step(step_num, f"Router Agent -> Customer Data Agent: \"{data_query}\"")
        step_num += 1
        
        task = SubTask(
            id="task_1",
            description="Simple data retrieval",
            agent="customer_data",
            query=data_query,
            depends_on=[]
        )
        sub_tasks.append(task)
        
        result = await self.execute_task(task, silent=True)
        
        if result.get("success"):
            task.status = TaskStatus.COMPLETED
            task.result = result
            self.task_results["task_1"] = result.get("content", {})
            
            content = result.get("content", {})
            if isinstance(content, dict) and content.get("operations"):
                for op in content.get("operations", []):
                    tool = op.get("tool", "unknown")
                    tools_used.append(tool)
                    op_result = op.get("result", {})
                    if op_result.get("success"):
                        data = op_result.get("data")
                        if isinstance(data, dict) and data.get("name"):
                            self.log_step(step_num, f"Customer Data Agent -> Router Agent: Returns \"{data.get('name')}\" (via MCP: {tool})")
                        elif isinstance(data, list):
                            self.log_step(step_num, f"Customer Data Agent -> Router Agent: Returns {len(data)} records (via MCP: {tool})")
                        else:
                            self.log_step(step_num, f"Customer Data Agent -> Router Agent: Returns data (via MCP: {tool})")
                        step_num += 1
        else:
            task.status = TaskStatus.FAILED
            self.log_step(step_num, "Customer Data Agent -> Router Agent: FAILED")
            step_num += 1
        
        self.log_step(step_num, "Router Agent returns response to user")
        
        return self._finalize_result(query, sub_tasks, tools_used, "Simple Query")
    
    async def _process_coordinated(self, query: str, analysis: Dict, step_num: int) -> OrchestrationResult:
        """Scenario 2: Coordinated Query - Multiple agents coordinate"""
        sub_tasks = []
        tools_used = []
        self.task_results = {}
        
        # Step 1: Router receives query
        self.log_step(step_num, f"Router Agent receives query: \"{query[:50]}{'...' if len(query) > 50 else ''}\"")
        step_num += 1
        
        # Step 2: Router -> Customer Data Agent to fetch customer info
        if analysis["customer_id"]:
            data_query = f"Get customer {analysis['customer_id']} information and history"
        else:
            data_query = "List customers"
        
        self.log_step(step_num, f"Router Agent -> Customer Data Agent: \"{data_query[:45]}...\"")
        step_num += 1
        
        task1 = SubTask(
            id="task_1",
            description="Fetch customer data",
            agent="customer_data",
            query=data_query,
            depends_on=[]
        )
        sub_tasks.append(task1)
        
        result1 = await self.execute_task(task1, silent=True)
        
        if result1.get("success"):
            task1.status = TaskStatus.COMPLETED
            task1.result = result1
            self.task_results["task_1"] = result1.get("content", {})
            
            content = result1.get("content", {})
            if isinstance(content, dict) and content.get("operations"):
                for op in content.get("operations", []):
                    tool = op.get("tool", "unknown")
                    tools_used.append(tool)
                    op_result = op.get("result", {})
                    if op_result.get("success"):
                        data = op_result.get("data")
                        if isinstance(data, dict):
                            name = data.get("customer", {}).get("name") if data.get("customer") else data.get("name", "data")
                            self.log_step(step_num, f"Customer Data Agent -> Router Agent: Returns customer \"{name}\" (via MCP: {tool})")
                        else:
                            self.log_step(step_num, f"Customer Data Agent -> Router Agent: Returns data (via MCP: {tool})")
                        step_num += 1
        else:
            task1.status = TaskStatus.FAILED
        
        # Step 3: Router -> Support Agent with customer context
        self.log_step(step_num, f"Router Agent -> Support Agent: \"Generate response with customer context\"")
        step_num += 1
        
        task2 = SubTask(
            id="task_2",
            description="Generate coordinated support response",
            agent="support",
            query=query,
            depends_on=["task_1"]
        )
        sub_tasks.append(task2)
        
        result2 = await self.execute_task(task2, silent=True)
        
        if result2.get("success"):
            task2.status = TaskStatus.COMPLETED
            task2.result = result2
            content = result2.get("content", {})
            if isinstance(content, dict) and content.get("response"):
                self.log_step(step_num, f"Support Agent -> Router Agent: Generates response ({len(content.get('response', ''))} chars)")
                step_num += 1
        else:
            task2.status = TaskStatus.FAILED
        
        self.log_step(step_num, "Router Agent returns coordinated response to user")
        
        return self._finalize_result(query, sub_tasks, tools_used, "Coordinated Query")
    
    async def _process_escalation(self, query: str, analysis: Dict, step_num: int) -> OrchestrationResult:
        """Scenario 4: Escalation - Identify urgency and route appropriately"""
        sub_tasks = []
        tools_used = []
        self.task_results = {}
        
        # Step 1: Router identifies urgency
        self.log_step(step_num, f"Router Agent receives URGENT query: \"{query[:40]}...\"")
        step_num += 1
        
        self.log_step(step_num, "Router Agent identifies: URGENCY DETECTED - Escalation required")
        step_num += 1
        
        # Step 2: Get customer context first (for billing issues)
        if analysis["customer_id"]:
            data_query = f"Get customer {analysis['customer_id']} billing information"
        else:
            data_query = "Get recent billing transactions"
        
        self.log_step(step_num, f"Router Agent -> Customer Data Agent: \"{data_query}\" [PRIORITY: HIGH]")
        step_num += 1
        
        task1 = SubTask(
            id="task_1",
            description="Get billing context for escalation",
            agent="customer_data",
            query=data_query,
            depends_on=[]
        )
        sub_tasks.append(task1)
        
        result1 = await self.execute_task(task1, silent=True)
        
        if result1.get("success"):
            task1.status = TaskStatus.COMPLETED
            task1.result = result1
            self.task_results["task_1"] = result1.get("content", {})
            
            content = result1.get("content", {})
            if isinstance(content, dict) and content.get("operations"):
                for op in content.get("operations", []):
                    tool = op.get("tool", "unknown")
                    tools_used.append(tool)
                    self.log_step(step_num, f"Customer Data Agent -> Router Agent: Returns billing context (via MCP: {tool})")
                    step_num += 1
        
        # Step 3: Escalate to Support Agent with HIGH priority
        self.log_step(step_num, f"Router Agent -> Support Agent: \"ESCALATION - Handle urgent refund request\"")
        step_num += 1
        
        escalation_query = f"URGENT ESCALATION: {query}. Customer requires immediate assistance. Priority: HIGH."
        
        task2 = SubTask(
            id="task_2",
            description="Handle escalated support request",
            agent="support",
            query=escalation_query,
            depends_on=["task_1"]
        )
        sub_tasks.append(task2)
        
        result2 = await self.execute_task(task2, silent=True)
        
        if result2.get("success"):
            task2.status = TaskStatus.COMPLETED
            task2.result = result2
            content = result2.get("content", {})
            if isinstance(content, dict) and content.get("response"):
                self.log_step(step_num, f"Support Agent -> Router Agent: Generates PRIORITY response ({len(content.get('response', ''))} chars)")
                step_num += 1
        
        self.log_step(step_num, "Router Agent returns escalated response to user [PRIORITY: HIGH]")
        
        return self._finalize_result(query, sub_tasks, tools_used, "Escalation (URGENT)")
    
    async def _process_multi_intent(self, query: str, analysis: Dict, step_num: int) -> OrchestrationResult:
        """Scenario 5: Multi-Intent - Parallel task execution and coordination"""
        sub_tasks = []
        tools_used = []
        self.task_results = {}
        
        # Step 1: Router detects multiple intents
        intents_str = " + ".join(analysis["intents"]) if analysis["intents"] else "update + fetch"
        self.log_step(step_num, f"Router Agent receives multi-intent query")
        step_num += 1
        
        self.log_step(step_num, f"Router Agent decomposes into parallel tasks: [{intents_str}]")
        step_num += 1
        
        # Task A: Update email (if requested)
        if analysis.get("update_data", {}).get("email"):
            email = analysis["update_data"]["email"]
            customer_id = analysis.get("customer_id", 3)  # Default to customer 3 if not specified
            
            self.log_step(step_num, f"Router Agent -> Customer Data Agent: \"Update customer {customer_id} email to {email}\" [PARALLEL A]")
            step_num += 1
            
            task_update = SubTask(
                id="task_update",
                description="Update customer email",
                agent="customer_data",
                query=f"Update customer {customer_id} email to {email}",
                depends_on=[]
            )
            sub_tasks.append(task_update)
            
            result_update = await self.execute_task(task_update, silent=True)
            
            if result_update.get("success"):
                task_update.status = TaskStatus.COMPLETED
                task_update.result = result_update
                self.task_results["task_update"] = result_update.get("content", {})
                
                content = result_update.get("content", {})
                if isinstance(content, dict) and content.get("operations"):
                    for op in content.get("operations", []):
                        tool = op.get("tool", "unknown")
                        tools_used.append(tool)
                        self.log_step(step_num, f"Customer Data Agent -> Router Agent: Email updated (via MCP: {tool}) [PARALLEL A DONE]")
                        step_num += 1
        
        # Task B: Get ticket history
        customer_id = analysis.get("customer_id", 3)
        self.log_step(step_num, f"Router Agent -> Customer Data Agent: \"Get ticket history for customer {customer_id}\" [PARALLEL B]")
        step_num += 1
        
        task_history = SubTask(
            id="task_history",
            description="Get customer ticket history",
            agent="customer_data",
            query=f"Get customer {customer_id} information and ticket history",
            depends_on=[]
        )
        sub_tasks.append(task_history)
        
        result_history = await self.execute_task(task_history, silent=True)
        
        if result_history.get("success"):
            task_history.status = TaskStatus.COMPLETED
            task_history.result = result_history
            self.task_results["task_history"] = result_history.get("content", {})
            
            content = result_history.get("content", {})
            if isinstance(content, dict) and content.get("operations"):
                for op in content.get("operations", []):
                    tool = op.get("tool", "unknown")
                    tools_used.append(tool)
                    op_result = op.get("result", {})
                    data = op_result.get("data", {})
                    ticket_count = len(data.get("tickets", [])) if isinstance(data, dict) else 0
                    self.log_step(step_num, f"Customer Data Agent -> Router Agent: Returns {ticket_count} tickets (via MCP: {tool}) [PARALLEL B DONE]")
                    step_num += 1
        
        # Step: Coordinate results
        self.log_step(step_num, "Router Agent coordinates parallel task results")
        step_num += 1
        
        self.log_step(step_num, "Router Agent returns combined response to user")
        
        return self._finalize_result(query, sub_tasks, tools_used, "Multi-Intent (Parallel Execution)")
    
    def _finalize_result(self, query: str, sub_tasks: List[SubTask], tools_used: List[str], scenario_name: str) -> OrchestrationResult:
        """Finalize and return orchestration result"""
        final_task = sub_tasks[-1] if sub_tasks else None
        final_response = ""
        
        if final_task and final_task.result and final_task.result.get("content"):
            content = final_task.result["content"]
            if isinstance(content, dict):
                if content.get("response"):
                    final_response = content["response"]
                else:
                    final_response = json.dumps(content, indent=2, default=str)
            else:
                final_response = str(content)
        
        # Print summary
        if self.verbose:
            print(f"\n  Summary:")
            print(f"   - Scenario: {scenario_name}")
            print(f"   - Agents used: {', '.join(set(t.agent for t in sub_tasks))}")
            if tools_used:
                print(f"   - MCP Tools called: {', '.join(tools_used)}")
            print(f"   - Status: {'SUCCESS' if all(t.status == TaskStatus.COMPLETED for t in sub_tasks) else 'FAILED'}")
        
        # Print final response
        if self.verbose and final_task and final_task.result and final_task.result.get("content"):
            self._print_structured_response(final_task.result["content"])
        
        return OrchestrationResult(
            query=query,
            sub_tasks=sub_tasks,
            final_response=final_response,
            success=all(t.status == TaskStatus.COMPLETED for t in sub_tasks)
        )
    
    def _print_structured_response(self, content):
        """Print response in a well-structured format"""
        print("\n" + "=" * 60)
        print("  FINAL RESPONSE")
        print("=" * 60)
        
        if isinstance(content, dict):
            agent = content.get("agent", "Unknown")
            print(f"\n  Agent: {agent}")
            
            # Customer Data Agent response
            if agent == "CustomerDataAgent":
                operations = content.get("operations", [])
                for op in operations:
                    tool = op.get("tool", "unknown")
                    result = op.get("result", {})
                    
                    print(f"\n  Tool: {tool}")
                    print("  " + "-" * 50)
                    
                    if result.get("success"):
                        data = result.get("data")
                        
                        # Single customer with tickets
                        if isinstance(data, dict) and data.get("customer"):
                            customer = data["customer"]
                            print(f"\n  Customer Information:")
                            print(f"    ID:      {customer.get('id')}")
                            print(f"    Name:    {customer.get('name')}")
                            print(f"    Email:   {customer.get('email')}")
                            print(f"    Phone:   {customer.get('phone', 'N/A')}")
                            print(f"    Status:  {customer.get('status')}")
                            
                            tickets = data.get("tickets", [])
                            if tickets:
                                print(f"\n  Tickets ({len(tickets)}):")
                                print("    " + "-" * 45)
                                for t in tickets[:5]:
                                    issue = t.get('issue', t.get('subject', 'N/A'))
                                    issue = issue[:40] if issue else 'N/A'
                                    print(f"    #{t.get('id')}: {issue}")
                                    print(f"        Priority: {t.get('priority')} | Status: {t.get('status')}")
                                if len(tickets) > 5:
                                    print(f"    ... and {len(tickets) - 5} more")
                        
                        # Single customer (no tickets)
                        elif isinstance(data, dict) and data.get("name"):
                            print(f"\n  Customer Information:")
                            print(f"    ID:      {data.get('id')}")
                            print(f"    Name:    {data.get('name')}")
                            print(f"    Email:   {data.get('email')}")
                            print(f"    Phone:   {data.get('phone', 'N/A')}")
                            print(f"    Status:  {data.get('status')}")
                        
                        # List of customers
                        elif isinstance(data, list) and len(data) > 0 and data[0].get("name"):
                            print(f"\n  Customers ({len(data)}):")
                            print("    " + "-" * 45)
                            for c in data[:5]:
                                print(f"    #{c.get('id')}: {c.get('name')} ({c.get('email')})")
                                print(f"        Status: {c.get('status')}")
                            if len(data) > 5:
                                print(f"    ... and {len(data) - 5} more")
                        
                        # List of tickets
                        elif isinstance(data, list) and len(data) > 0 and (data[0].get("issue") or data[0].get("subject") or data[0].get("priority")):
                            print(f"\n  Tickets ({len(data)}):")
                            print("    " + "-" * 45)
                            for t in data[:5]:
                                issue = t.get('issue', t.get('subject', 'N/A'))
                                issue = issue[:40] if issue else 'N/A'
                                print(f"    #{t.get('id')}: {issue}")
                                print(f"        Customer: {t.get('customer_id')} | Priority: {t.get('priority')} | Status: {t.get('status')}")
                            if len(data) > 5:
                                print(f"    ... and {len(data) - 5} more")
                        
                        else:
                            # Generic data
                            print(f"\n  Data:")
                            print(f"    {json.dumps(data, indent=4, default=str)[:500]}")
                    else:
                        print(f"  Error: {result.get('error', 'Unknown error')}")
            
            # Support Agent response
            elif agent == "SupportAgent":
                response_text = content.get("response", "")
                if response_text:
                    print(f"\n  Response:")
                    print("  " + "-" * 50)
                    for line in response_text.split('\n'):
                        wrapped = textwrap.wrap(line, width=54) or ['']
                        for w in wrapped:
                            print(f"  | {w}")
                    print("  " + "-" * 50)
            
            else:
                # Unknown agent format
                print(f"\n  Content:")
                print(f"  {json.dumps(content, indent=2, default=str)[:800]}")
        
        else:
            print(f"\n  {content}")
        
        print("\n" + "=" * 60)


# ============================================================================
# Interactive Demo
# ============================================================================

async def interactive_demo():
    """Run interactive orchestrator demo"""
    print("\n" + "=" * 70)
    print("  A2A Multi-Agent Orchestrator")
    print("=" * 70)
    print("  Commands: 'demo' for all scenarios, 'quit' to exit")
    print("=" * 70)
    
    orchestrator = Orchestrator(verbose=True)
    await orchestrator.initialize()
    
    demo_scenarios = [
        ("1. Simple Query", "Get customer information for ID 5"),
        ("2. Coordinated Query", "I'm customer 5 and need help upgrading my account"),
        ("3. Complex Query", "Show me all active customers who have open tickets"),
        ("4. Escalation", "I've been charged twice, please refund immediately!"),
        ("5. Multi-Intent", "Update my email to new@email.com and show my ticket history for customer 3"),
    ]
    
    while True:
        try:
            query = input("\n> ").strip()
            
            if query.lower() == 'quit':
                print("Goodbye!")
                break
            
            if query.lower() == 'demo':
                for name, q in demo_scenarios:
                    print(f"\n{'=' * 70}")
                    print(f"  Scenario {name}")
                    print(f"  Query: \"{q}\"")
                    print("=" * 70)
                    await orchestrator.process_query(q)
                    print("\n" + "-" * 70)
                    input("  Press Enter to continue...")
                continue
            
            if not query:
                continue
            
            await orchestrator.process_query(query)
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    asyncio.run(interactive_demo())