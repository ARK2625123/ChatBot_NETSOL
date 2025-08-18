# app/agent/langgraph_agent.py
from typing import TypedDict, Literal, List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from ..search.tavily_search import tavily_searcher
from ..llm.gemini import ask_gemini
import json

class AgentState(TypedDict):
    messages: List[Any]
    user_query: str
    decision: Literal["rag", "search", "both"]
    rag_context: str
    search_results: List[Dict]
    final_answer: str
    user_id: str

class ChatbotAgent:
    def __init__(self, rag_retriever_func):
        self.rag_retriever_func = rag_retriever_func
        self.graph = self._create_graph()
    
    def _create_graph(self):
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("decide_tool", self.decide_tool)
        workflow.add_node("use_rag", self.use_rag)
        workflow.add_node("use_search", self.use_search)
        workflow.add_node("use_both", self.use_both)
        workflow.add_node("generate_answer", self.generate_answer)
        
        # Set entry point
        workflow.set_entry_point("decide_tool")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "decide_tool",
            self.route_decision,
            {
                "rag": "use_rag",
                "search": "use_search", 
                "both": "use_both"
            }
        )
        
        # All paths lead to generate_answer
        workflow.add_edge("use_rag", "generate_answer")
        workflow.add_edge("use_search", "generate_answer")
        workflow.add_edge("use_both", "generate_answer")
        workflow.add_edge("generate_answer", END)
        
        return workflow.compile()
    
    def decide_tool(self, state: AgentState) -> AgentState:
        """Decide whether to use RAG, search, or both"""
        user_query = state["user_query"]
        
        decision_prompt = f"""
        Analyze this user query and decide what tool(s) to use:
        
        Query: "{user_query}"
        
        Decision criteria:
        - Use "rag" for: questions about uploaded documents, internal company info, financial analysis of provided docs
        - Use "search" for: current events, latest news, real-time information, general web knowledge
        - Use "both" for: queries that might benefit from both document analysis AND current information
        
        Examples:
        - "What's in my financial report?" -> rag
        - "What's the current stock price of AAPL?" -> search  
        - "How does my company's performance compare to current market trends?" -> both
        
        Respond with ONLY one word: rag, search, or both
        """
        
        try:
            decision = ask_gemini(decision_prompt).strip().lower()
            if decision not in ["rag", "search", "both"]:
                decision = "rag"  # default fallback
        except:
            decision = "rag"  # default fallback
        
        state["decision"] = decision
        return state
    
    def route_decision(self, state: AgentState) -> str:
        return state["decision"]
    
    def use_rag(self, state: AgentState) -> AgentState:
        """Use RAG to get context from uploaded documents"""
        try:
            user_id = state["user_id"]
            query = state["user_query"]
            
            # Get RAG context using the retriever function
            rag_context, _ = self.rag_retriever_func(user_id, query)
            state["rag_context"] = rag_context
        except Exception as e:
            print(f"RAG error: {e}")
            state["rag_context"] = "No relevant documents found."
        
        return state
    
    def use_search(self, state: AgentState) -> AgentState:
        """Use Tavily to search the web"""
        try:
            query = state["user_query"]
            search_results = tavily_searcher.search(query, max_results=3)
            state["search_results"] = search_results
        except Exception as e:
            print(f"Search error: {e}")
            state["search_results"] = []
        
        return state
    
    def use_both(self, state: AgentState) -> AgentState:
        """Use both RAG and search"""
        state = self.use_rag(state)
        state = self.use_search(state)
        return state
    
    def generate_answer(self, state: AgentState) -> AgentState:
        """Generate final answer based on available context"""
        user_query = state["user_query"]
        decision = state["decision"]
        
        # Build context based on what tools were used
        context_parts = []
        
        if decision in ["rag", "both"] and state.get("rag_context"):
            context_parts.append(f"DOCUMENT CONTEXT:\n{state['rag_context']}")
        
        if decision in ["search", "both"] and state.get("search_results"):
            search_context = "\n\n".join([
                f"SOURCE: {r['title']} ({r['url']})\n{r['content']}"
                for r in state["search_results"][:3]
            ])
            context_parts.append(f"WEB SEARCH RESULTS:\n{search_context}")
        
        if not context_parts:
            context_parts.append("No additional context available.")
        
        full_context = "\n\n" + "="*50 + "\n\n".join(context_parts)
        
        final_prompt = f"""
        You are a helpful financial analyst assistant. Answer the user's question using the provided context.
        
        User Question: {user_query}
        
        Context: {full_context}
        
        Instructions:
        - Provide a clear, concise answer (2-4 sentences)
        - If using document context, focus on that information
        - If using web search, include relevant current information
        - If no relevant context is available, say so clearly
        - Be honest about limitations
        
        Answer:
        """
        
        try:
            answer = ask_gemini(final_prompt).strip()
            state["final_answer"] = answer
        except Exception as e:
            print(f"Answer generation error: {e}")
            state["final_answer"] = "I apologize, but I encountered an error while generating the response."
        
        return state
    
    def run(self, user_query: str, user_id: str) -> str:
        """Run the complete agent workflow"""
        initial_state = {
            "messages": [],
            "user_query": user_query,
            "decision": "rag",
            "rag_context": "",
            "search_results": [],
            "final_answer": "",
            "user_id": user_id
        }
        
        try:
            result = self.graph.invoke(initial_state)
            return result["final_answer"]
        except Exception as e:
            print(f"Agent workflow error: {e}")
            return "I apologize, but I encountered an error while processing your request."