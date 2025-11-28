"""
Support Agent - A2A Server
Independent A2A service for customer support response generation
Uses OpenAI for response generation.
"""

import json
import re
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

# Lazy OpenAI client
_openai_client = None

def get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI()
    return _openai_client


class SupportAgentExecutor(AgentExecutor):
    """Generates customer support responses using LLM."""
    
    async def execute(self, context, event_queue):
        """Handle A2A request"""
        query = context.get_user_input()
        
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
        
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        
        try:
            response = self._generate_response(query)
            result = {"agent": "SupportAgent", "response": response}
            response_text = json.dumps(result, indent=2, default=str)
            
            text_part = Part(root=TextPart(text=response_text))
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
    
    def _generate_response(self, query):
        """Generate response using LLM"""
        # Extract context data if present
        context_data = None
        actual_query = query
        
        try:
            if "{" in query:
                json_match = re.search(r'\{.*\}', query, re.DOTALL)
                if json_match:
                    context_data = json.loads(json_match.group())
                    actual_query = query[:json_match.start()].strip() or "Process the data"
        except:
            pass
        
        system_prompt = """You are a professional Customer Support Agent.
Your responsibilities:
- Provide helpful, friendly responses
- If customer data is provided, personalize your response
- Format ticket information in clear tables when appropriate
- Confirm updates and provide next steps
- Be concise and professional"""
        
        user_message = f"Query: {actual_query}"
        if context_data:
            user_message += f"\n\nContext Data:\n{json.dumps(context_data, indent=2, default=str)}"
        
        try:
            client = get_openai_client()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"I apologize, but I encountered an issue: {str(e)}"


def create_agent_card(host, port):
    """Create the A2A Agent Card"""
    skills = [
        AgentSkill(id="generate_response", name="Generate Support Response",
                   description="Generate helpful customer support responses",
                   tags=["support", "response"], examples=["Help with my account"]),
        AgentSkill(id="format_data", name="Format Data",
                   description="Format customer or ticket data",
                   tags=["format", "data"], examples=["Format ticket list"]),
        AgentSkill(id="handle_complaint", name="Handle Complaint",
                   description="Process customer complaints",
                   tags=["complaint", "issue"], examples=["I have a problem"]),
    ]
    
    return AgentCard(
        name="Support Agent",
        description="Agent for customer support with LLM response generation",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=skills,
    )


def run_server(host="localhost", port=8002):
    """Run the Support Agent A2A Server"""
    agent_executor = SupportAgentExecutor()
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
    print("Support Agent - A2A Server")
    print("=" * 60)
    print(f"Agent Card: http://{host}:{port}/.well-known/agent.json")
    print("=" * 60)
    
    uvicorn.run(a2a_app.build(), host=host, port=port)


if __name__ == "__main__":
    port = 8002
    
    # Parse command line args
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
    
    run_server(port=port)
