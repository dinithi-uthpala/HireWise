"""Information Retrieval package.

- vector_store.py   ChromaDB client + collection + persistence
- skill_taxonomy.py canonical skill names + synonym normalization
                     ("MS Excel" -> Excel, "Structured Query Language" -> SQL)
- knowledge_base.py load seed documents from knowledge_base/docs/ into Chroma

Each agent queries the vector store to retrieve competency frameworks,
scoring rubrics and skill definitions instead of inventing them.
"""