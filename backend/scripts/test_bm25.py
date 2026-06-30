from pinecone_text.sparse import BM25Encoder

bm25 = BM25Encoder.default()
docs = ["Hello world", "This is a test"]
res = bm25.encode_documents(docs)
print("Docs:", res)

q = bm25.encode_queries("Hello")
print("Query:", q)
