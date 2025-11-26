"""
Comprehensive Test Suite for Multi-Agent Customer Service System
Demonstrates all required scenarios with detailed A2A coordination

IMPORTANT: Run 'python database_setup.py' first to create support.db
"""

import json
import os
from typing import Dict, Any
from multi_agent_system import process_query
from mcp_server import mcp_server

def print_section_header(title: str):
    """Print formatted section header"""
    print("\n" + "="*100)
    print(f" {title} ".center(100, "="))
    print("="*100 + "\n")

def print_result(result: Dict):
    """Print query result in formatted way"""
    print(f"Query: {result['query']}")
    print(f"\nAgent Messages Exchanged: {result['messages_exchanged']}")
    print(f"\n{'─'*100}")
    print("COORDINATION LOG:")
    print('─'*100)
    for log in result['coordination_log']:
        print(f"  {log}")
    print('─'*100)
    print(f"\nFINAL RESPONSE TO CUSTOMER:")
    print('─'*100)
    print(result['response'])
    print('─'*100)
    
    # Show retrieved data if available
    if result.get('customer_data'):
        print(f"\nCustomer Data Retrieved:")
        customer_data = result['customer_data']
        if isinstance(customer_data, dict) and customer_data.get('type') == 'list':
            # List of customers
            customers = customer_data.get('customers', [])
            print(f"  Total Customers: {len(customers)}")
            for idx, c in enumerate(customers[:10], 1):  # Show up to 10 customers
                print(f"    {idx}. {c.get('name')} ({c.get('email')}) - {c.get('status')}")
            if len(customers) > 10:
                print(f"    ... and {len(customers) - 10} more")
        else:
            # Single customer
            print(json.dumps(customer_data, indent=2))
    
    if result.get('tickets'):
        tickets = result['tickets']
        print(f"\nTickets Retrieved: {len(tickets)}")
        for idx, t in enumerate(tickets[:15], 1):  # Show up to 15 tickets
            issue = t.get('issue', 'N/A')
            issue_display = issue[:50] + "..." if len(issue) > 50 else issue
            customer_name = t.get('customer_name', 'Unknown')
            print(f"    {idx}. [{t.get('priority', 'N/A').upper()}] {issue_display}")
            print(f"       Customer: {customer_name} | Status: {t.get('status', 'N/A')}")
        if len(tickets) > 15:
            print(f"    ... and {len(tickets) - 15} more tickets")
        
        # Show summary
        open_count = sum(1 for t in tickets if t.get('status') == 'open')
        in_progress = sum(1 for t in tickets if t.get('status') == 'in_progress')
        resolved = sum(1 for t in tickets if t.get('status') == 'resolved')
        print(f"\n    Summary: Total={len(tickets)}, Open={open_count}, In Progress={in_progress}, Resolved={resolved}")

def run_all_tests():
    """Run all test scenarios"""
    
    print_section_header("INITIALIZING SYSTEM")
    
    # Check if database exists
    if not os.path.exists('support.db'):
        print("❌ ERROR: Database 'support.db' not found!")
        print("\nPlease run the following command first:")
        print("  python database_setup.py")
        print("\nThen run this test script again.")
        return
    
    print("✅ Database 'support.db' found!")
    print("✅ MCP Server ready with tools:", mcp_server.list_tools())
    
    # ============================================================================
    # TEST SCENARIO 1: Simple Query - Single Agent
    # ============================================================================
    print_section_header("TEST SCENARIO 1: Simple Query (Single Agent)")
    print("Expected Flow: Router → Customer Data Agent → Final Response")
    print("Tests: Single agent, straightforward MCP call\n")
    
    result = process_query("Get customer information for ID 5", verbose=False)
    print_result(result)
    
    # ============================================================================
    # TEST SCENARIO 2: Task Allocation
    # ============================================================================
    print_section_header("TEST SCENARIO 2: Task Allocation")
    print("Expected Flow: Router → Customer Data → Support → Final Response")
    print("Tests: Multiple agents coordinate, data fetch + support response\n")
    
    result = process_query("I need help with my account, customer ID 3", verbose=False)
    print_result(result)
    
    # ============================================================================
    # TEST SCENARIO 3: Coordinated Query
    # ============================================================================
    print_section_header("TEST SCENARIO 3: Coordinated Query (Account Upgrade)")
    print("Expected Flow: Router → Customer Data → Support → Final Response")
    print("Tests: Multiple agents coordinate with context passing\n")
    
    result = process_query("I'm customer 1 and need help upgrading my account", verbose=False)
    print_result(result)
    
    # ============================================================================
    # TEST SCENARIO 4: Complex Multi-Step Query
    # ============================================================================
    print_section_header("TEST SCENARIO 4: Complex Query (Multiple Data Sources)")
    print("Expected Flow: Router → Customer Data (multiple MCP calls) → Support → Final")
    print("Tests: Requires negotiation between data and support agents\n")
    
    result = process_query("Show me all active customers who have high priority open tickets", verbose=False)
    print_result(result)
    
    # ============================================================================
    # TEST SCENARIO 5: Escalation Query
    # ============================================================================
    print_section_header("TEST SCENARIO 5: Escalation (Urgent Issue)")
    print("Expected Flow: Router (high priority) → Customer Data → Support (urgent) → Final")
    print("Tests: Router identifies urgency and routes appropriately\n")
    
    result = process_query("I've been charged twice for my subscription! This is urgent, customer ID 2", verbose=False)
    print_result(result)
    
    # ============================================================================
    # TEST SCENARIO 6: Multi-Intent Query
    # ============================================================================
    print_section_header("TEST SCENARIO 6: Multi-Intent Query")
    print("Expected Flow: Router → Customer Data → Support (handles both intents) → Final")
    print("Tests: Parallel task execution and coordination\n")
    
    result = process_query("I'm customer 7, update my email to newemail@example.com and show my ticket history", verbose=False)
    print_result(result)
    
    # ============================================================================
    # TEST SCENARIO 7: Negotiation/Escalation
    # ============================================================================
    print_section_header("TEST SCENARIO 7: Negotiation (Multiple Intents)")
    print("Expected Flow: Router detects multiple intents → coordinates agents → Final")
    print("Tests: Cancellation + billing issues require agent negotiation\n")
    
    result = process_query("I want to cancel my subscription but I'm having billing issues, ID 5", verbose=False)
    print_result(result)
    
    # ============================================================================
    # TEST SCENARIO 8: Complex Data Aggregation
    # ============================================================================
    print_section_header("TEST SCENARIO 8: Multi-Step Coordination (Data Aggregation)")
    print("Expected Flow: Router → Data (customers) → Data (high priority tickets) → Support → Final")
    print("Tests: Router decomposes task, agents coordinate for report\n")
    
    # First, let's create some high-priority tickets for active customers
    print("Setting up test data: Creating high-priority tickets for active customers...")
    mcp_server.call_tool('create_ticket', customer_id=1, issue="Urgent: System access problems", priority='high')
    mcp_server.call_tool('create_ticket', customer_id=5, issue="Critical billing error", priority='high')
    mcp_server.call_tool('create_ticket', customer_id=7, issue="Service outage impacting business", priority='high')
    print("Test tickets created.\n")
    
    result = process_query("What's the status of all high-priority tickets for active customers?", verbose=False)
    print_result(result)

    for tool in mcp_server.list_tools():
        print(f"  • {tool}")
    print("\n" + "="*100)

if __name__ == '__main__':
    run_all_tests()