import json
import os
import glob
from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from termcolor import cprint
from ingest_ids import memory_point_id

class GeminiIngester:
    def __init__(self, collection_name="atlas_eternal"):
        self.collection_name = collection_name
        self.client = QdrantClient("localhost", port=6333)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.ensure_collection()

    def ensure_collection(self):
        try:
            self.client.get_collection(self.collection_name)
        except:
            cprint(f" Creating collection: {self.collection_name}", "yellow")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
            )

    def parse_session_json(self, filepath: str) -> List[Dict]:
        """Parses Gemini CLI session JSON."""
        conversations = []
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                if 'messages' in data:
                    return data['messages']
        except Exception as e:
            cprint(f"Error reading {filepath}: {e}", "red")
        return []

    def ingest_directory(self, tmp_dir: str):
        # Pattern: ~/.gemini/tmp/*/chats/*.json
        pattern = os.path.join(tmp_dir, "**", "chats", "*.json")
        files = glob.glob(pattern, recursive=True)
        
        cprint(f"Found {len(files)} Gemini session files.", "cyan")
        
        total_points = 0
        
        for filepath in tqdm(files, desc="Ingesting Atlas Memories"):
            msgs = self.parse_session_json(filepath)
            if not msgs: continue

            points = []
            
            for i in range(len(msgs) - 1):
                curr = msgs[i]
                next_msg = msgs[i+1]
                
                # Check for Human -> AI flow
                role_curr = curr.get('type')
                role_next = next_msg.get('type')
                
                if role_curr == 'user' and role_next == 'gemini':
                    user_text = curr.get('content', '')
                    ai_text = next_msg.get('content', '')
                    
                    if not user_text or not ai_text: continue
                    
                    # Embed
                    embedding = self.model.encode(user_text).tolist()
                    
                    payload = {
                        "platform": "gemini",
                        "user_input": user_text,
                        "ai_response": ai_text,
                        "source_file": os.path.basename(filepath),
                        "timestamp": curr.get('timestamp', '') 
                    }
                    
                    points.append(models.PointStruct(
                        id=memory_point_id(filepath, user_text, ai_text),
                        vector=embedding,
                        payload=payload
                    ))
            
            if points:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                total_points += len(points)
                
        cprint(f"✅ Ingested {total_points} memories into {self.collection_name}", "green")

if __name__ == "__main__":
    gemini_path = os.path.expanduser("~/.gemini/tmp") 
    ingester = GeminiIngester()
    ingester.ingest_directory(gemini_path)
