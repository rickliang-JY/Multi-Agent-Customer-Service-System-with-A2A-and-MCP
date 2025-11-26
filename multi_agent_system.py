"""
Multi-Agent Customer Service System with LangGraph
Implements Router, Customer Data, and Support agents with A2A coordination
"""

from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
# from langchain_anthropic import ChatAnthropic  # Anthropic version
from langchain_openai import ChatOpenAI  # OpenAI version
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import operator
import json
from mcp_server import mcp_server

# State definition for the multi-agent system
class AgentState(TypedDict):
    """Shared state across all agents"""
    # Input
    query: str
    
    # Agent communication
    messages: Annotated[List[Dict[str, Any]], operator.add]
    current_agent: str
    next_agent: Optional[str]
    
    # Data storage
    customer_data: Optional[Dict[str, Any]]
    tickets: Optional[List[Dict[str, Any]]]
    
    # Final response
    final_response: str
    
    # Coordination metadata
    coordination_log: Annotated[List[str], operator.add]
    task_type: Optional[str]

# Initialize LLM - Using OpenAI GPT
# If using Anthropic Claude, use:
# from langchain_anthropic import ChatAnthropic
# llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)

# Using OpenAI GPT:
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o", temperature=0)  # or "gpt-4-turbo" or "gpt-3.5-turbo"

# Agent Implementations

class RouterAgent:
    """
    Router Agent (Orchestrator)
    - Receives customer queries
    - Analyzes query intent
    - Routes to appropriate specialist agent
    - Coordinates responses from multiple agents
    """
    
    def __init__(self):
        self.name = "Router"
        
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze query to determine intent and routing"""
        
        system_prompt = """You are a Router Agent in a customer service system.

Your job is to analyze customer queries and determine:
1. The type of task (data_retrieval, update, support, complex_multi_step)
2. Which specialist agents are needed (customer_data, support, or both)
3. The priority level (low, medium, high)

IMPORTANT ROUTING RULES:
- If query mentions "get", "show", "retrieve", "find", "customer ID", "information for ID" → route to customer_data
- If query asks about data but doesn't provide specific info → route to customer_data
- If query is about support, help, problems, issues (without specific ID) → route to support
- If query involves multiple operations → route to customer_data first

Respond with ONLY a JSON object (no markdown, no explanation):
{
    "task_type": "data_retrieval|update|support|complex_multi_step",
    "agents_needed": ["customer_data"],
    "priority": "low|medium|high",
    "requires_customer_id": true,
    "reasoning": "brief explanation"
}"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Analyze this customer query: {query}")
        ]
        
        response = llm.invoke(messages)
        
        # Parse JSON response - handle markdown code blocks
        try:
            content = response.content.strip()
            # Remove markdown code blocks if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            analysis = json.loads(content)
        except Exception as e:
            # Smart fallback based on keywords
            query_lower = query.lower()
            
            # Data retrieval patterns
            data_keywords = ['get', 'show', 'retrieve', 'find', 'customer id', 'id', 'information for', 
                           'list', 'all', 'customers', 'tickets', 'priority', 'status', 'history']
            
            if any(kw in query_lower for kw in data_keywords):
                analysis = {
                    "task_type": "data_retrieval",
                    "agents_needed": ["customer_data"],
                    "priority": "high" if 'urgent' in query_lower or 'high' in query_lower else "medium",
                    "requires_customer_id": 'id' in query_lower,
                    "reasoning": "Data retrieval query detected by keyword matching"
                }
            else:
                analysis = {
                    "task_type": "support",
                    "agents_needed": ["support"],
                    "priority": "medium",
                    "requires_customer_id": False,
                    "reasoning": "General support query"
                }
        
        return analysis
    
    def __call__(self, state: AgentState) -> AgentState:
        """Process state and route to appropriate agent"""
        
        query = state['query']
        
        # Log entry
        log_entry = f"[ROUTER] Received query: {query}"
        state['coordination_log'].append(log_entry)
        
        # Analyze query
        analysis = self.analyze_query(query)
        
        log_entry = f"[ROUTER] Analysis: {analysis['task_type']}, Agents needed: {analysis['agents_needed']}"
        state['coordination_log'].append(log_entry)
        
        # Store task type
        state['task_type'] = analysis['task_type']
        
        # Determine next agent
        agents_needed = analysis['agents_needed']
        
        if 'customer_data' in agents_needed:
            state['next_agent'] = 'customer_data'
            log_entry = "[ROUTER] Routing to Customer Data Agent"
        elif 'support' in agents_needed:
            state['next_agent'] = 'support'
            log_entry = "[ROUTER] Routing to Support Agent"
        else:
            state['next_agent'] = 'support'
            log_entry = "[ROUTER] Default routing to Support Agent"
        
        state['coordination_log'].append(log_entry)
        state['current_agent'] = 'router'
        
        # Add message for next agent
        state['messages'].append({
            "from": "router",
            "to": state['next_agent'],
            "content": f"Please handle this query: {query}",
            "analysis": analysis
        })
        
        return state


class CustomerDataAgent:
    """
    Customer Data Agent (Specialist)
    - Accesses customer database via MCP
    - Retrieves customer information
    - Updates customer records
    - Handles data validation
    """
    
    def __init__(self):
        self.name = "CustomerData"
        
    def extract_customer_id(self, text: str) -> Optional[int]:
        """Extract customer ID from text"""
        import re
        # Look for patterns like "customer ID 123", "ID 123", "customer 123"
        patterns = [
            r'customer\s+id\s+(\d+)',
            r'id\s+(\d+)',
            r'customer\s+(\d+)',
            r'#(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return int(match.group(1))
        
        return None
    
    def __call__(self, state: AgentState) -> AgentState:
        """Process customer data requests"""
        
        query = state['query']
        query_lower = query.lower()
        
        log_entry = f"[CUSTOMER DATA] Processing request"
        state['coordination_log'].append(log_entry)
        
        # Extract customer ID if present
        customer_id = self.extract_customer_id(query)
        
        # Determine what data to fetch based on query
        response_data = {}
        
        # Priority 1: Specific customer ID mentioned
        if customer_id:
            # Fetch customer info
            customer_info = mcp_server.call_tool('get_customer', customer_id=customer_id)
            state['customer_data'] = customer_info
            response_data['customer'] = customer_info
            
            log_entry = f"[CUSTOMER DATA] Retrieved customer {customer_id}: {customer_info.get('name', 'Unknown')}"
            state['coordination_log'].append(log_entry)
            
            # Check if we need ticket history for this customer
            if any(keyword in query_lower for keyword in ['ticket', 'history', 'issue', 'problem']):
                history = mcp_server.call_tool('get_customer_history', customer_id=customer_id)
                state['tickets'] = history.get('tickets', [])
                response_data['history'] = history
                
                log_entry = f"[CUSTOMER DATA] Retrieved {len(state['tickets'])} tickets for customer {customer_id}"
                state['coordination_log'].append(log_entry)
        
        # Priority 2: Query about high-priority tickets (no specific customer)
        elif any(kw in query_lower for kw in ['high-priority', 'high priority', 'priority']) and 'ticket' in query_lower:
            # Get high priority tickets
            high_priority_tickets = mcp_server.call_tool('get_tickets_by_priority', priority='high')
            state['tickets'] = high_priority_tickets
            response_data['high_priority_tickets'] = high_priority_tickets
            
            log_entry = f"[CUSTOMER DATA] Retrieved {len(high_priority_tickets)} high priority tickets"
            state['coordination_log'].append(log_entry)
            
            # Also get active customers if mentioned
            if any(kw in query_lower for kw in ['customer', 'active']):
                customers = mcp_server.call_tool('list_customers', status='active', limit=20)
                response_data['customers'] = customers
                state['customer_data'] = {"type": "list", "customers": customers, "count": len(customers)}
                
                log_entry = f"[CUSTOMER DATA] Retrieved {len(customers)} active customers"
                state['coordination_log'].append(log_entry)
        
        # Priority 3: Query about tickets in general
        elif 'ticket' in query_lower:
            # Determine priority level
            if 'high' in query_lower:
                priority = 'high'
            elif 'medium' in query_lower:
                priority = 'medium'
            elif 'low' in query_lower:
                priority = 'low'
            else:
                priority = 'high'  # Default to high priority
            
            # Determine status filter
            status = None
            if 'open' in query_lower:
                status = 'open'
            elif 'resolved' in query_lower:
                status = 'resolved'
            elif 'in_progress' in query_lower or 'in progress' in query_lower:
                status = 'in_progress'
            
            tickets = mcp_server.call_tool('get_tickets_by_priority', priority=priority, status=status)
            state['tickets'] = tickets
            response_data['tickets'] = tickets
            
            log_entry = f"[CUSTOMER DATA] Retrieved {len(tickets)} {priority} priority tickets"
            state['coordination_log'].append(log_entry)
        
        # Priority 4: List operations for customers
        elif any(kw in query_lower for kw in ['all', 'list', 'show', 'customers', 'active']):
            status_filter = 'active' if 'active' in query_lower else None
            customers = mcp_server.call_tool('list_customers', status=status_filter, limit=20)
            response_data['customers'] = customers
            
            # Store in customer_data so Support Agent can access it
            state['customer_data'] = {"type": "list", "customers": customers, "count": len(customers)}
            
            log_entry = f"[CUSTOMER DATA] Retrieved {len(customers)} customers"
            state['coordination_log'].append(log_entry)
            
            # Check if we also need tickets
            if 'ticket' in query_lower or 'priority' in query_lower:
                high_priority_tickets = mcp_server.call_tool('get_tickets_by_priority', priority='high', status='open')
                response_data['high_priority_tickets'] = high_priority_tickets
                state['tickets'] = high_priority_tickets
                
                log_entry = f"[CUSTOMER DATA] Retrieved {len(high_priority_tickets)} high priority open tickets"
                state['coordination_log'].append(log_entry)
        
        # Priority 5: Update operations
        elif 'update' in query_lower or 'change' in query_lower:
            log_entry = "[CUSTOMER DATA] Update operation detected - requires Support Agent coordination"
            state['coordination_log'].append(log_entry)
            state['next_agent'] = 'support'
        
        # Default: Try to get something useful
        else:
            customers = mcp_server.call_tool('list_customers', status='active', limit=10)
            state['customer_data'] = {"type": "list", "customers": customers, "count": len(customers)}
            
            log_entry = f"[CUSTOMER DATA] Default: Retrieved {len(customers)} active customers"
            state['coordination_log'].append(log_entry)
        
        state['current_agent'] = 'customer_data'
        
        # Always route to Support Agent for response generation
        # Support Agent will use the data we collected to generate a proper response
        state['next_agent'] = 'support'
        
        log_entry = "[CUSTOMER DATA] Forwarding to Support Agent for response generation"
        state['coordination_log'].append(log_entry)
        
        # Add message for next agent
        state['messages'].append({
            "from": "customer_data",
            "to": "support",
            "content": "Customer data retrieved",
            "data": response_data
        })
        
        return state


class SupportAgent:
    """
    Support Agent (Specialist)
    - Handles general customer support queries
    - Can escalate complex issues
    - Requests customer context from Data Agent
    - Provides solutions and recommendations
    """
    
    def __init__(self):
        self.name = "Support"
        
    def generate_response(self, state: AgentState) -> str:
        """Generate final customer response using LLM"""
        
        query = state['query']
        customer_data = state.get('customer_data')
        tickets = state.get('tickets', [])
        messages_history = state.get('messages', [])
        
        # Build context
        context_parts = [f"Customer Query: {query}\n"]
        
        if customer_data:
            # Handle both single customer and list of customers
            if isinstance(customer_data, dict) and customer_data.get('type') == 'list':
                # List of customers
                customers = customer_data.get('customers', [])
                context_parts.append(f"Customer List ({len(customers)} active customers):\n")
                for idx, c in enumerate(customers[:20], 1):  # Show up to 20 customers
                    context_parts.append(f"  {idx}. {c.get('name')} - {c.get('email')} - Phone: {c.get('phone')} - Status: {c.get('status')}\n")
                if len(customers) > 20:
                    context_parts.append(f"  ... and {len(customers) - 20} more customers\n")
            else:
                # Single customer
                context_parts.append(f"Customer Information: {json.dumps(customer_data, indent=2)}\n")
        
        if tickets:
            context_parts.append(f"\nTicket Information ({len(tickets)} tickets):\n")
            for idx, ticket in enumerate(tickets[:20], 1):  # Show up to 20 tickets
                customer_name = ticket.get('customer_name', 'Unknown')
                context_parts.append(f"  {idx}. [{ticket.get('priority', 'N/A').upper()}] {ticket.get('issue')} - Customer: {customer_name} - Status: {ticket.get('status')}\n")
            if len(tickets) > 20:
                context_parts.append(f"  ... and {len(tickets) - 20} more tickets\n")
            
            # Add summary statistics
            open_count = sum(1 for t in tickets if t.get('status') == 'open')
            in_progress_count = sum(1 for t in tickets if t.get('status') == 'in_progress')
            resolved_count = sum(1 for t in tickets if t.get('status') == 'resolved')
            context_parts.append(f"\n  Summary: Total={len(tickets)}, Open={open_count}, In Progress={in_progress_count}, Resolved={resolved_count}\n")
        
        context = "\n".join(context_parts)
        
        system_prompt = """You are a Support Agent in a customer service system.
        
Your job is to:
1. Provide helpful, professional responses to customer queries
2. Use customer data and history when available
3. IMPORTANT: If data is provided (customer list, tickets), include ALL the actual data in your response
4. Format lists clearly with the actual information
5. Be specific and actionable

CRITICAL RULES FOR DATA DISPLAY:
- When ticket data is provided, you MUST list ALL tickets (up to 20), not just a few examples
- When customer data is provided, include relevant customer details
- Do not give generic instructions like "check your dashboard" - show the actual data!
- Include a summary at the end with totals and statistics

Example format for tickets:
| # | Customer | Issue | Status | Priority |
|---|----------|-------|--------|----------|
| 1 | John Doe | Login issues | Open | High |
| 2 | Jane Smith | Billing error | In Progress | High |
... (list ALL tickets)

**Summary:**
- Total tickets: X
- Open: Y
- In Progress: Z
- Resolved: W

Generate a comprehensive response that includes ALL relevant data."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=context)
        ]
        
        response = llm.invoke(messages)
        
        return response.content
    
    def __call__(self, state: AgentState) -> AgentState:
        """Process support requests and generate response"""
        
        log_entry = "[SUPPORT] Generating customer response"
        state['coordination_log'].append(log_entry)
        
        # Check if we need customer data
        query = state['query']
        customer_data = state.get('customer_data')
        tickets = state.get('tickets')
        
        # If we have data (either customer_data or tickets), we can proceed
        has_data = customer_data is not None or (tickets is not None and len(tickets) > 0)
        
        # If query mentions customer ID but we don't have data, request it ONCE
        if not has_data and any(kw in query.lower() for kw in ['customer', 'id', 'account', 'active', 'all', 'show', 'list']):
            # Check if customer_data agent already ran
            went_to_data = any(msg.get('from') == 'customer_data' for msg in state.get('messages', []))
            
            # Only request data if we haven't already been to customer_data agent
            if not went_to_data:
                log_entry = "[SUPPORT] Need customer data - requesting from Customer Data Agent"
                state['coordination_log'].append(log_entry)
                state['next_agent'] = 'customer_data'
                state['current_agent'] = 'support'
                
                state['messages'].append({
                    "from": "support",
                    "to": "customer_data",
                    "content": "Need customer data for this query"
                })
                
                return state
            else:
                # Already went to data agent but no data - proceed without it
                log_entry = "[SUPPORT] Customer data not available - proceeding with general response"
                state['coordination_log'].append(log_entry)
        
        # Log what data we have
        if customer_data:
            if isinstance(customer_data, dict) and customer_data.get('type') == 'list':
                log_entry = f"[SUPPORT] Using customer list data ({customer_data.get('count', 0)} customers)"
            else:
                log_entry = f"[SUPPORT] Using single customer data"
            state['coordination_log'].append(log_entry)
        
        if tickets:
            log_entry = f"[SUPPORT] Using ticket data ({len(tickets)} tickets)"
            state['coordination_log'].append(log_entry)
        
        # Generate response
        response = self.generate_response(state)
        
        state['final_response'] = response
        state['current_agent'] = 'support'
        state['next_agent'] = 'final'
        
        log_entry = "[SUPPORT] Response generated - completing workflow"
        state['coordination_log'].append(log_entry)
        
        return state


# Build LangGraph workflow

def create_workflow():
    """Create the multi-agent workflow graph"""
    
    workflow = StateGraph(AgentState)
    
    # Initialize agents
    router = RouterAgent()
    customer_data = CustomerDataAgent()
    support = SupportAgent()
    
    # Add nodes
    workflow.add_node("router", router)
    workflow.add_node("customer_data", customer_data)
    workflow.add_node("support", support)
    
    # Maximum iterations to prevent infinite loops
    MAX_ITERATIONS = 10
    
    # Define routing logic with loop detection
    def route_after_router(state: AgentState) -> str:
        """Route from router to next agent"""
        # Check iteration count to prevent infinite loops
        iteration_count = len([msg for msg in state.get('messages', []) if msg.get('from') == 'router'])
        if iteration_count > MAX_ITERATIONS:
            state['coordination_log'].append(f"[ROUTER] Max iterations ({MAX_ITERATIONS}) reached - forcing to support")
            return 'support'
        
        next_agent = state.get('next_agent', 'support')
        if next_agent == 'final':
            return END
        return next_agent
    
    def route_after_customer_data(state: AgentState) -> str:
        """Route from customer_data to next agent"""
        next_agent = state.get('next_agent', 'support')
        if next_agent == 'final':
            return END
        return next_agent
    
    def route_after_support(state: AgentState) -> str:
        """Route from support to next agent"""
        # Check if we've already been to customer_data
        went_to_data = any(msg.get('from') == 'customer_data' for msg in state.get('messages', []))
        
        next_agent = state.get('next_agent', 'final')
        if next_agent == 'customer_data' and not went_to_data:
            return 'customer_data'
        return END
    
    # Add edges
    workflow.set_entry_point("router")
    workflow.add_conditional_edges(
        "router",
        route_after_router,
        {
            "customer_data": "customer_data",
            "support": "support",
            END: END
        }
    )
    workflow.add_conditional_edges(
        "customer_data",
        route_after_customer_data,
        {
            "support": "support",
            END: END
        }
    )
    workflow.add_conditional_edges(
        "support",
        route_after_support,
        {
            "customer_data": "customer_data",
            END: END
        }
    )
    
    return workflow.compile()


# Main execution function

def process_query(query: str, verbose: bool = True) -> Dict[str, Any]:
    """
    Process a customer query through the multi-agent system
    
    Args:
        query: Customer query string
        verbose: Print coordination log
        
    Returns:
        Dictionary with response and metadata
    """
    
    # Initialize state
    initial_state = {
        "query": query,
        "messages": [],
        "current_agent": None,
        "next_agent": None,
        "customer_data": None,
        "tickets": None,
        "final_response": "",
        "coordination_log": [],
        "task_type": None
    }
    
    # Create and run workflow
    app = create_workflow()
    final_state = app.invoke(initial_state)
    
    if verbose:
        print("\n" + "="*80)
        print("MULTI-AGENT COORDINATION LOG")
        print("="*80)
        for log_entry in final_state['coordination_log']:
            print(log_entry)
        print("="*80 + "\n")
    
    return {
        "query": query,
        "response": final_state['final_response'],
        "coordination_log": final_state['coordination_log'],
        "customer_data": final_state.get('customer_data'),
        "tickets": final_state.get('tickets'),
        "messages_exchanged": len(final_state['messages'])
    }


if __name__ == '__main__':
    # Test queries
    test_queries = [
        "Get customer information for ID 5",
        "I'm customer 12345 and need help upgrading my account",
        "Show me all active customers who have open tickets",
    ]
    
    for query in test_queries:
        print(f"\n\nProcessing: {query}")
        result = process_query(query, verbose=True)
        print(f"\nFinal Response:\n{result['response']}")
        print("\n" + "-"*80)