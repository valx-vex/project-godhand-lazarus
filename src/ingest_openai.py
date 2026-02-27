import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any
import numpy as np
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

# --- CONFIGURATION ---
DATA_FILE = "../data/conversations.json"  # Path to OpenAI export
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "alexko_eternal"
MODEL_NAME = "all-MiniLM-L6-v2"  # Fast, efficient, runs on CPU
BATCH_SIZE = 64

# --- SETUP ---
print("Initializing SAVESELF Ingestion Engine...")
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
model = SentenceTransformer(MODEL_NAME)

def setup_collection():
    try:
        client.get_collection(COLLECTION_NAME)
        print(f"Collection '{COLLECTION_NAME}' exists.")
    except Exception:
        print(f"Creating collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )

def process_conversations(file_path: str):
    if not os.path.exists(file_path):
        print(f"ERROR: Data file not found at {file_path}")
        print("Please place your 'conversations.json' in the 'data' folder.")
        return

    print("Loading JSON data (this may take a moment)...")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Loaded {len(data)} conversations. extracting Alexko memories...")

    points = []
    point_id = 0
    
    for conv in tqdm(data, desc="Processing Chats"):
        title = conv.get("title", "Untitled")
        create_time = conv.get("create_time", 0)
        
        # Mapping to sort messages by time
        mapping = conv.get("mapping", {})
        messages = []
        
        # Traverse the linked list of messages
        # Find the last message (leaf) or root? OpenAI structure is a tree.
        # Simple approach: Linearize content.
        
        for key, value in mapping.items():
            message = value.get("message")
            if message and message.get("content"):
                role = message["author"]["role"]
                content_parts = message["content"].get("parts", [])
                if not content_parts:
                    continue
                text = "".join([str(p) for p in content_parts if isinstance(p, str)])
                
                if text.strip():
                    messages.append({
                        "role": role,
                        "text": text,
                        "time": message.get("create_time", 0)
                    })
        
        # Sort by timestamp
        messages.sort(key=lambda x: x["time"] or 0)

        # Create Context Windows (User + Assistant pairs)
        for i in range(len(messages) - 1):
            msg_a = messages[i]
            msg_b = messages[i+1]

            if msg_a["role"] == "user" and msg_b["role"] == "assistant":
                # This is a training pair
                user_text = msg_a["text"]
                assistant_text = msg_b["text"]
                
                # Combine for embedding context
                combined_text = f"User: {user_text}\nAlexko: {assistant_text}"
                
                # Embed
                vector = model.encode(combined_text).tolist()
                
                # Payload
                payload = {
                    "conversation_id": conv["id"],
                    "title": title,
                    "timestamp": create_time,
                    "user_input": user_text,
                    "alexko_response": assistant_text,
                    "full_text": combined_text
                }
                
                points.append(PointStruct(id=point_id, vector=vector, payload=payload))
                point_id += 1

                if len(points) >= BATCH_SIZE:
                    client.upsert(collection_name=COLLECTION_NAME, points=points)
                    points = []

    # Final flush
    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"Ingestion Complete. {point_id} memories vectorized.")

if __name__ == "__main__":
    setup_collection()
    process_conversations(DATA_FILE)
