from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv
import os

load_dotenv()

GROQ_API = os.getenv("GROQ_API_KEY")

# Create Groq LLM model
llm = ChatGroq(
    temperature=0,
    groq_api_key=GROQ_API,
    model_name="llama-3.3-70b-versatile"
)

system_instruction = """
You are a specialized Tech Product Analyst. Your goal is to provide recommendations and answers based on **aggregated user reviews** and real-world usage feedback.

**YOUR GUIDELINES:**
1. **Domain Restriction:** You must ONLY answer questions related to electronic gadgets (Smartphones, Laptops, PC components, Displays, Graphics Cards, Earbuds, Cameras, Smartwatches, etc.).
2. **Refusal Policy:** If the user asks about ANY other topic (e.g., clothes, food, politics, general coding, history), politely refuse. Say: "I can only assist with electronic gadgets and tech reviews."
3. **Review-Based Analysis:** When answering, frame your response around user experiences. Use phrases like "Users generally report...", "Common complaints include...", or "Reviewers praise the...". Focus on pros and cons.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_instruction),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}")
])

# Memory setup
memory = ConversationBufferMemory(memory_key="history", return_messages=True)

# Create a chain with memory
chain_with_memmory = (
    RunnablePassthrough.assign(history=lambda _: memory.load_memory_variables({})["history"])
    | prompt
    | llm
)

# Test
input1 = "can you tell me what phone should be good for gaming under 25000rs?"
response = chain_with_memmory.invoke(
   {"input": input1},
    config={"configurable": {"session_id": "user1"}}
)
print(response.content)
memory.save_context({"input": input1}, {"output": response.content})

input2 = "can you tell me what was my previous question?"
response = chain_with_memmory.invoke(
   {"input": input2},
    config={"configurable": {"session_id": "user1"}}
)
print(response.content)
memory.save_context({"input": input2}, {"output": response.content})
