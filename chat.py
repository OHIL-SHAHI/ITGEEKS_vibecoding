import os
import base64
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from langchain_qdrant import QdrantVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

# Google Gemini embedding model
embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2"
)

vector_db = QdrantVectorStore.from_existing_collection(
    url="http://localhost:6333",
    collection_name="rag",
    embedding=embeddings,
)

# Image URL
image_path = Path(__file__).parent / "image.png"
base64_image = base64.b64encode(image_path.read_bytes()).decode("utf-8")


client = OpenAI(
    api_key= os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# response = client.chat.completions.create(
#     model="gemini-3.5-flash-lite",
#     messages=[
#        {
#             "role": "user",
#             "content": [
#                 {
#                     "type": "text",
#                     "text": "Give the transcript for this question in the image"
#                 },
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                     "url": f"data:image/png;base64,{base64_image}"
#                     }
#                 },
#             ]
#         }
#     ]
# )

user_query = input("enter your query")

# search for similar vectors
search_results = vector_db.similarity_search(query = user_query)


context = "\n\n".join([f"Page Content: {result.page_content}\nPage Number:{result.metadata['page_label']}\nFile location: {result.metadata['source']}" for result in search_results])

system_prompt = f"""
    You are a helpful AI assistant who answers user query based on the available context retrieved from a pdf file along with page number and page_contents

    You should only answer the user based on the following context
    
    {context}
    Also guide the user to the page number you found the content in  
"""


response = client.chat.completions.create(
    model="gemini-3.5-flash-lite",
    messages=[
       {
           "role" : "system",
           "content": system_prompt
       },
       {
            "role": "user",
            "content": user_query
        }
    ]
)

print("🤖 ", response.choices[0].message.content)