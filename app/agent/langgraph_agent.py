from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from ..search.tavily_search import TavilySearcher
from ..rag.retriever import MultiUserRetriever
import os

class ReactAgent:
    def __init__(self,MultiUserRetriever):
        
        self.multiuser_retriever = MultiUserRetriever #Giving bro the retriebver function

        self.llm=ChatGoogleGenerativeAI(  #kinda initializing the llm, giving it all the good stuff
            model="gemini-1.5-flash",
            temperature=0.1,
            google_api_key=os.getenv("GOOGLE_API_KEY"))
        
       

        self.tools= self.create_tools()  #gonna use this to initialize the tools which we will use
        
        self.agent=create_react_agent(  #actually putting the good stuff in our agent
            tools=self.tools,
            model=self.llm,
            prompt= self._get_system_message())      #had to do this cuz it wasnt working when i pass state modifier directly to it

    def _get_system_message(self):
        return SystemMessage( #the code of conduct, kinda like the crystals from Superman (1978)
            content="You are a helpful assistant and a financial analyst. You can answer questions about uploaded financial documents or search the web,or do both at once for users.Be concise and precise when answering questions. If you don't know the answer, say 'I don't know'. When searching the web use the TavilySearcher tool and when retrieving info from uploaded documents use the MultiUserRetriever tool.",
        )
    

    def create_tools(self) -> list:  #now we connect it to the rest of app, allowing it to get and "create" the tools needed

        @tool
        def document_searcher(query:str)-> str:
             """
            Search through the user's uploaded documents for relevant information.
            Use this for questions about financial reports, company documents, or any uploaded files.
            Args:
                query: The search query to find relevant document content  
            Returns:
                str: Relevant content from the user's documents
            """  #more code of conduct SHOULD ASK QUESTIONS ABOUT THIS
             
             try:
                 user_id=getattr(self, 'current_id','user1') #we need the id to call the retriever functions BUT WHY WE SENDING USER1????
                 rag_context, raw_docs = self.multiuser_retriever.query_user_documents(user_id, query, 4) #function gives us the context and docs which we will use next

                 if rag_context and rag_context.strip():
                     sources=[]
                     if raw_docs:
                         for doc in raw_docs[:4]:          #we no go through all, just first 4 docs
                                source = doc.metadata.get("source", "unknown")  
                                page = doc.metadata.get("page","N/A")
                                sources.append(f"{source} (Page {page})")  #we got the source and page of the doc (if available) BUT GOTTA ASK MORE ABOUT THIS

                     result=rag_context
                     if sources:
                         result += "\n\nSources:\n" + "\n".join(sources)  #concatination time! but only if we have sources hence the if
                     return result
                 else:
                     return "No relevant information found in your documents."
             except Exception as e:
                 return f"Error retrieving documents: {str(e)}"    
             

        @tool
        def live_searcher(query: str) -> str:
            """
            Search the internet for current information, news, stock prices, market data, etc.
            Use this for questions about current events, latest news, real-time information, or general knowledge.
            Args:
                query: The search query for web search 
            Returns:
                str: Relevant information from web search results
            """ #again more code of conduct NEED TO KNOW about this

            try:
                search_results = TavilySearcher().search(query,max_results=4)  #using the existing TavilySearcher class to search and get the top 4 results
                if not search_results:
                    return "lets test this."
                else:
                    s_result= []
                    for i,result in enumerate(search_results[:3],1):   #iterate through the search results, get their info and throw em in the s_results
                        title=result.get("title", "No title")
                        content=result.get("content", "No available content")
                        url=result.get("url", "No URL")
                        s_result.append(f"Result {i}: {title}Content: {content}...Source: {url}")
                    return "\n\n".join(s_result)  #return the search results as a string
            
            except Exception as e:
                return f"Error searching web: {str(e)}"
            
        return [live_searcher, document_searcher]  #we create new tools using existing tools (MINECRAFT STYLE) and then return them as a list
        #also dont need to manually bind them to the agent as im using the create_react_agent function which does it automatically
    
    def run(self, uquery: str, user_id: str) -> str:

        try:
            self._current_id_ = user_id  #get from arg and put it here so we can use in tool, specifically in the doc search
            messages=[HumanMessage(content=uquery)]  #create a message with uquery as its contents
            result = self.agent.invoke({
                "messages": messages})  #WAKE MY HOMEBOY UP and give him the messages

            if result and "messages" in result:
                for message in reversed (result["messages"]):  #reverse the messages cuz what we want is in the last one
                    if hasattr(message, 'content') and message.content:  #Grand Operation: check if the message has content     
                        if not any (x in message.content.lower()
                                    for x in ["action:", "observation:", "thought:"]):
                            return message.content  #if the content is not empty and does not contain any of the processing stuff, LADIES AND GENTLEMEN, WE GOT EM
                        
        
            else:
                return "No valid response from agent." #else we wrong
        
        except Exception as e:
            print(f"Agent error: {e}")
            return f"I encountered an error while processing your request: {str(e)}"
