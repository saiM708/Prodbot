from langchain_astradb import AstraDBVectorStore
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
import os
from prodbot.data_converter import dataconverter
from dotenv import load_dotenv
load_dotenv()

GROQ_API=os.getenv("GROQ_API")
ASTRA_DB_API_ENDPOINT=os.getenv("ASTRA_DB_API_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN=os.getenv("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_DB_KEYSPACE=os.getenv("ASTRA_DB_KEYSPACE")
HF_TOKEN = os.getenv("HF_TOKEN")

local_embeddings = HuggingFaceBgeEmbeddings(model_name="all-MiniLM-L6-v2")

def data_ingestion(status):

    vstore = AstraDBVectorStore(
        embedding=local_embeddings,
        collection_name = "flipkart",
        api_endpoint = ASTRA_DB_API_ENDPOINT,
        token = ASTRA_DB_APPLICATION_TOKEN,
        namespace = ASTRA_DB_KEYSPACE 
    )

    storage = status

    if storage == None:
        docs = dataconverter()
        insert_ids = vstore.add_documents(docs)
    
    else:
        return vstore
    return vstore, insert_ids

if __name__ == "__main__":

    vstore, insert_ids = data_ingestion(None)
    print(f"\n Inserted {len(insert_ids)} documents.")
    results = vstore.similarity_search("Can you tell me the low budget waterproof earbuds?")
    for res in results:
        print(f"\n {res.page_content} [{res.metadata}]")