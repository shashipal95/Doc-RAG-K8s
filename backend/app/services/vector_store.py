# backend/app/services/vector_store.py
"""
Vector Store Service
Qdrant operations for document storage and retrieval.
Supports hybrid search (dense + sparse) combined using Reciprocal Rank Fusion (RRF).
"""
from typing import Dict, List
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    Fusion,
    FusionQuery,
    MatchValue,
    PointStruct,
    Prefetch,
    SparseVectorParams,
    VectorParams,
)

from app.core.config import get_settings

settings = get_settings()

# Initialize Qdrant Client
client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
collection_name = settings.QDRANT_COLLECTION_NAME


def string_to_uuid(s: str) -> str:
    """Generate a deterministic UUID from a string (such as the document chunk ID)."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, s))


def setup_index():
    """Create collection in Qdrant if it doesn't exist"""
    try:
        collections_res = client.get_collections()
        existing = [c.name for c in collections_res.collections]
    except Exception as e:
        print(f"[vector_store] Error listing collections: {e}. Attempting creation directly.")
        existing = []

    if collection_name not in existing:
        metric_str = settings.QDRANT_METRIC.lower()
        if metric_str == "dotproduct":
            distance = Distance.DOT
        elif metric_str == "cosine":
            distance = Distance.COSINE
        else:
            distance = Distance.EUCLID

        print(f"[vector_store] Creating collection '{collection_name}' with dense vector dimension {settings.QDRANT_DIMENSION} and metric {distance}...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=settings.QDRANT_DIMENSION,
                    distance=distance
                )
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams()
            }
        )
        print(f"[vector_store] Collection '{collection_name}' created successfully.")
    else:
        print(f"[vector_store] Connected to existing collection '{collection_name}'.")


# Set up the index synchronously on module load
try:
    setup_index()
except Exception as e:
    print(f"[vector_store] Collection setup deferred: {e}")


def upsert_vectors(
    vectors: List[Dict],
    namespace: str
) -> int:
    """
    Insert or update vectors in Qdrant
    
    Args:
        vectors: List of vector dicts with id, values, sparse_values, metadata
        namespace: User namespace for data isolation
        
    Returns:
        Number of vectors upserted
    """
    from qdrant_client.models import SparseVector

    points = []
    for v in vectors:
        vector_data = {
            "dense": v["values"]
        }

        # Handle sparse vector if provided
        sparse_val = v.get("sparse_values")
        if sparse_val and sparse_val.get("indices") and sparse_val.get("values"):
            vector_data["sparse"] = SparseVector(
                indices=sparse_val["indices"],
                values=sparse_val["values"]
            )

        # Merge namespace into payload for data isolation
        payload = {
            "namespace": namespace,
            **v["metadata"]
        }

        points.append(PointStruct(
            id=string_to_uuid(v["id"]),
            vector=vector_data,
            payload=payload
        ))

    client.upsert(
        collection_name=collection_name,
        points=points
    )
    return len(vectors)


def query_vectors(
    query_vector: List[float],
    namespace: str,
    top_k: int = 3,
    filter: Dict = None,
    sparse_vector: Dict = None,
) -> List[Dict]:
    """
    Query similar vectors from Qdrant.
    Uses Reciprocal Rank Fusion (RRF) hybrid query if sparse vector is present.
    """
    from qdrant_client.models import SparseVector

    # 1. Base filter condition for multi-tenant namespace isolation
    filter_conditions = [
        FieldCondition(
            key="namespace",
            match=MatchValue(value=namespace)
        )
    ]

    # Translate simple exact-match filters if provided (e.g. {"filename": fname})
    if filter:
        for k, v in filter.items():
            filter_conditions.append(
                FieldCondition(
                    key=k,
                    match=MatchValue(value=v)
                )
            )

    qdrant_filter = Filter(must=filter_conditions)

    # Check if sparse query is available
    has_sparse = (
        sparse_vector is not None 
        and len(sparse_vector.get("indices", [])) > 0 
        and len(sparse_vector.get("values", [])) > 0
    )

    if has_sparse:
        # Prefetch dense matches
        prefetch_dense = Prefetch(
            query=query_vector,
            using="dense",
            limit=top_k * 2,
            filter=qdrant_filter
        )
        # Prefetch sparse matches
        prefetch_sparse = Prefetch(
            query=SparseVector(
                indices=sparse_vector["indices"],
                values=sparse_vector["values"]
            ),
            using="sparse",
            limit=top_k * 2,
            filter=qdrant_filter
        )

        # Run hybrid search on Qdrant using RRF
        results = client.query_points(
            collection_name=collection_name,
            prefetch=[prefetch_dense, prefetch_sparse],
            query=FusionQuery(
                fusion=Fusion.RRF
            ),
            limit=top_k
        )
        points = results.points
    else:
        # Fallback to standard dense search
        results = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            using="dense",
            query_filter=qdrant_filter,
            limit=top_k
        )
        points = results.points

    # Map Qdrant points format back to expected dict format:
    # {"id": str, "score": float, "metadata": dict}
    matches = []
    for p in points:
        matches.append({
            "id": str(p.id),
            "score": p.score,
            "metadata": {k: v for k, v in p.payload.items()}
        })
    return matches


def delete_all_user_vectors(namespace: str):
    """Delete all vectors for a user namespace."""
    try:
        client.delete(
            collection_name=collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="namespace",
                            match=MatchValue(value=namespace)
                        )
                    ]
                )
            )
        )
    except Exception as e:
        print(f"[vector_store] Delete all user vectors failed: {e}")
        raise


def delete_vectors_by_filter(namespace: str, filter: Dict):
    """Delete vectors matching a filter within a namespace."""
    try:
        filter_conditions = [
            FieldCondition(key="namespace", match=MatchValue(value=namespace))
        ]
        for k, v in filter.items():
            filter_conditions.append(
                FieldCondition(key=k, match=MatchValue(value=v))
            )
        client.delete(
            collection_name=collection_name,
            points_selector=FilterSelector(
                filter=Filter(must=filter_conditions)
            )
        )
    except Exception as e:
        print(f"[vector_store] Delete by filter failed: {e}")


def update_vectors_metadata(namespace: str, filter: Dict, new_metadata: Dict):
    """Update metadata/payload for all vectors matching a filter."""
    try:
        filter_conditions = [
            FieldCondition(key="namespace", match=MatchValue(value=namespace))
        ]
        for k, v in filter.items():
            filter_conditions.append(
                FieldCondition(key=k, match=MatchValue(value=v))
            )
        client.set_payload(
            collection_name=collection_name,
            payload=new_metadata,
            points=FilterSelector(
                filter=Filter(must=filter_conditions)
            )
        )
        print(f"[vector_store] Updated metadata for vectors in {namespace} matching filter {filter}")
    except Exception as e:
        print(f"[vector_store] Update metadata failed: {e}")


def fetch_all_vectors_by_filter(namespace: str, filter: Dict) -> List[Dict]:
    """Fetch all vectors matching a filter (e.g. all chunks of a filename)."""
    try:
        filter_conditions = [
            FieldCondition(key="namespace", match=MatchValue(value=namespace))
        ]
        for k, v in filter.items():
            filter_conditions.append(
                FieldCondition(key=k, match=MatchValue(value=v))
            )

        res, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(must=filter_conditions),
            limit=10000,
            with_payload=True,
            with_vectors=True
        )

        matches = []
        for p in res:
            dense_values = []
            if isinstance(p.vector, dict) and "dense" in p.vector:
                dense_values = p.vector["dense"]
            elif isinstance(p.vector, list):
                dense_values = p.vector

            matches.append({
                "id": str(p.id),
                "values": dense_values,
                "metadata": p.payload
            })
        return matches
    except Exception as e:
        print(f"[vector_store] Fetch by filter failed: {e}")
        return []


class QdrantStats:
    def __init__(self, total_vector_count: int, dimension: int, index_fullness: float):
        self.total_vector_count = total_vector_count
        self.dimension = dimension
        self.index_fullness = index_fullness


def get_index_stats():
    """Get statistics of the Qdrant collection modeled as index stats."""
    try:
        collection_info = client.get_collection(collection_name)
        vectors_config = collection_info.config.params.vectors
        dimension = 3072
        if isinstance(vectors_config, dict):
            if "dense" in vectors_config:
                dimension = vectors_config["dense"].size
        else:
            dimension = getattr(vectors_config, "size", 3072)

        return QdrantStats(
            total_vector_count=collection_info.points_count,
            dimension=dimension,
            index_fullness=0.0
        )
    except Exception as e:
        print(f"[vector_store] Get stats failed: {e}")
        return QdrantStats(
            total_vector_count=0,
            dimension=settings.QDRANT_DIMENSION,
            index_fullness=0.0
        )