from qdrant_client import QdrantClient


# Option B: Persistent Local Path (Data is saved into a local folder, like SQLite)
client = QdrantClient(path="./local_qdrant_storage")

# Now you can interact with it exactly like a regular server setup!
# client.create_collection(...)