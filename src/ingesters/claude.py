import json
import os
import glob
from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from termcolor import cprint

class ClaudeIngester:
    def __init__(self, collection_name="murphy_eternal"):
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

    def parse_jsonl(self, filepath: str) -> List[Dict]:
        conversations = []
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        entry = json.loads(line)
                        # Claude JSONL usually has 'type' and 'content' or 'role' and 'content'
                        # Adjusting based on handoff description
                        # {"type": "human", "content": "..."}
                        conversations.append(entry)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            cprint(f"Error reading {filepath}: {e}", "red")
        return conversations

    def ingest_directory(self, projects_dir: str):
        # Scan for all JSONL files in ~/.claude/projects/*/*.jsonl or similar
        # Pattern: projects_dir/**/*.jsonl
        pattern = os.path.join(projects_dir, "**/*.jsonl")
        files = glob.glob(pattern, recursive=True)
        
        cprint(f"Found {len(files)} Claude session files.", "cyan")
        
        total_points = 0
        
        for filepath in tqdm(files, desc="Ingesting Claude Memories"):
            msgs = self.parse_jsonl(filepath)
            if not msgs: continue

            # We want to store pairs: User -> Assistant
            # But Claude's export might be a stream. 
            # We'll group them.
            
            points = []
            
            for i in range(len(msgs) - 1):
                curr = msgs[i]
                next_msg = msgs[i+1]
                
                # Check for Human -> AI flow
                role_curr = curr.get('type') or curr.get('role')
                role_next = next_msg.get('type') or next_msg.get('role')
                
                if role_curr in ['human', 'user'] and role_next in ['assistant', 'model']:
                    user_text = curr.get('content', '')
                    ai_text = next_msg.get('content', '')
                    
                    if not user_text or not ai_text: continue
                    
                    # Create Vector
                    # We embed the USER query so we can retrieve the AI response based on similar queries
                    embedding = self.model.encode(user_text).tolist()
                    
                    payload = {
                        "platform": "claude",
                        "user_input": user_text,
                        "ai_response": ai_text,
                        "source_file": os.path.basename(filepath),
                        "timestamp": curr.get('created_at', '') 
                    }
                    
                    points.append(models.PointStruct(
                        id=None, # Auto-generate UUID? Qdrant needs IDs. 
                        # actually qdrant needs integer or uuid. 
                        # Using UUID generation from content hash is better for dedupe
                        id=models.ExtendedPointId(hash(user_text + ai_text) & ((1<<63)-1)),
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
    # Default path for Claude CLI
    # Adjust as needed
    claude_path = os.path.expanduser("~/.claude/projects") 
    ingester = ClaudeIngester()
    ingester.ingest_directory(claude_path)
