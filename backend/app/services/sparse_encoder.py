# backend/app/services/sparse_encoder.py
"""
Simple Sparse Encoder
Pure Python implementation of token frequency encoding with FNV-1a hashing.
Used to mock BM25Encoder without compilation/native dependencies.
"""
import re
from typing import Dict, List, Union


class SimpleSparseEncoder:
    def __init__(self):
        # Standard English stop words
        self.stop_words = {
            "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "arent",
            "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "cant",
            "cannot", "could", "couldnt", "did", "didnt", "do", "does", "doesnt", "doing", "dont", "down", "during",
            "each", "few", "for", "from", "further", "had", "hadnt", "has", "hasnt", "have", "havent", "having",
            "he", "hed", "hell", "hes", "her", "here", "heres", "hers", "herself", "him", "himself", "his", "how",
            "hows", "i", "id", "ill", "im", "ive", "if", "in", "into", "is", "isnt", "it", "its", "itself", "lets",
            "me", "more", "most", "mustnt", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
            "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shant", "she", "shed",
            "shell", "shes", "should", "shouldnt", "so", "some", "such", "than", "that", "thats", "the", "their",
            "theirs", "them", "themselves", "then", "there", "theres", "these", "they", "theyd", "theyll", "theyre",
            "theyve", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasnt", "we",
            "wed", "well", "were", "weve", "werent", "what", "whats", "when", "whens", "where", "wheres", "which",
            "while", "who", "whos", "whom", "why", "whys", "with", "wont", "would", "wouldnt", "you", "youd", "youll",
            "youre", "youve", "your", "yours", "yourself", "yourselves"
        }

    def _tokenize(self, text: str) -> List[str]:
        # lowercase and extract words
        tokens = re.findall(r'\b\w+\b', text.lower())
        return [t for t in tokens if t not in self.stop_words and len(t) > 1]

    def _hash_word(self, word: str) -> int:
        # FNV-1a 32-bit hash function mapped to 0..2^31 - 1 for safety with signed integer indexes
        h = 0x811c9dc5
        for char in word.encode("utf-8"):
            h = h ^ char
            h = (h * 0x01000193) & 0xffffffff
        return h & 0x7fffffff

    def encode_documents(self, documents: Union[str, List[str]]) -> List[Dict[str, Union[List[int], List[float]]]]:
        if isinstance(documents, str):
            documents = [documents]
            
        results = []
        for doc in documents:
            tokens = self._tokenize(doc)
            if not tokens:
                results.append({"indices": [], "values": []})
                continue
                
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
                
            doc_len = len(tokens)
            sorted_terms = sorted(tf.items())
            
            indices = []
            values = []
            for term, count in sorted_terms:
                idx = self._hash_word(term)
                val = float(count) / doc_len
                indices.append(idx)
                values.append(val)
                
            results.append({"indices": indices, "values": values})
        return results

    def encode_queries(self, queries: Union[str, List[str]]) -> Union[Dict[str, Union[List[int], List[float]]], List[Dict[str, Union[List[int], List[float]]]]]:
        is_single = isinstance(queries, str)
        if is_single:
            queries = [queries]
            
        results = []
        for q in queries:
            tokens = self._tokenize(q)
            if not tokens:
                results.append({"indices": [], "values": []})
                continue
                
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
                
            doc_len = len(tokens)
            sorted_terms = sorted(tf.items())
            
            indices = []
            values = []
            for term, count in sorted_terms:
                idx = self._hash_word(term)
                val = float(count) / doc_len
                indices.append(idx)
                values.append(val)
                
            results.append({"indices": indices, "values": values})
            
        return results[0] if is_single else results


class BM25Encoder:
    @staticmethod
    def default() -> SimpleSparseEncoder:
        return SimpleSparseEncoder()
