import json
import os
import glob
from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from termcolor import cprint
from ingest_eras import configured_murphy_era
from ingest_ids import memory_point_id

QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))

class ClaudeIngester:
    def __init__(self, collection_name="murphy_eternal"):
        self.collection_name = collection_name
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
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
                    
                    # Create Vector - embed combined text for richer semantic search
                    combined = f"User: {user_text}\nAssistant: {ai_text}"
                    embedding = self.model.encode(combined).tolist()
                    
                    payload = {
                        "platform": "claude",
                        "user_input": user_text,
                        "ai_response": ai_text,
                        "source_file": os.path.basename(filepath),
                        "timestamp": curr.get('created_at', ''),
                        "era": configured_murphy_era(filepath),
                    }
                    
                    point_id = memory_point_id(filepath, user_text, ai_text)

                    points.append(models.PointStruct(
                        id=point_id,
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
