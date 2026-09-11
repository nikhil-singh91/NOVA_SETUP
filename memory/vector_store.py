"""Semantic memory layer for NOVA.

This module implements :class:`VectorStore`, the component
responsible for finding the *most relevant* pieces of information
NOVA has stored, as opposed to
:class:`~memory.memory_manager.MemoryManager`, which is responsible
for storing and exactly retrieving them. Where ``MemoryManager``
answers "what did I store under this key?", ``VectorStore`` answers
"what do I know that is relevant to this query?".

Backend:
    This implementation uses a local, in-memory, lexical
    term-frequency similarity index. It depends on no external vector
    database and no network call, so it is available immediately and
    for free. It is deliberately isolated behind a small, stable
    public API (:meth:`VectorStore.add_document`,
    :meth:`VectorStore.search`, and so on) so that a future backend —
    ChromaDB, FAISS, Qdrant, Pinecone, or SQLite VSS — can replace the
    internal indexing and similarity logic entirely without requiring
    any change to :class:`~memory.memory_manager.MemoryManager` or any
    other caller. Nothing outside this module ever sees a raw
    embedding, index structure, or similarity computation directly.

Independence:
    ``VectorStore`` has no dependency on
    :class:`~memory.memory_manager.MemoryManager` or any other NOVA
    subsystem, and no other module needs to import from
    ``VectorStore`` for it to function. Any coordination between the
    two (for example, indexing a memory entry's text as soon as it is
    added) happens by having the caller invoke both managers' public
    methods; there is no circular import between them.
"""

from __future__ import annotations

import math
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Final, Literal, Mapping, Sequence


from core.exceptions import MemorySystemError as MemoryError
from core.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_TOP_K: Final[int] = 5
_MIN_SIMILARITY: Final[float] = 0.0
_MAX_SIMILARITY: Final[float] = 1.0
_DEFAULT_MIN_SIMILARITY: Final[float] = 0.0

# Matches runs of alphanumeric characters, used to tokenize text for
# the term-frequency similarity model. This is an intentionally
# simple tokenizer; a future embedding-backed implementation would
# replace token-based matching entirely.
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"[a-z0-9]+")

SearchMode = Literal["semantic", "exact", "partial"]

# A sentinel used by update_document to distinguish "this field was
# not provided" from "this field was explicitly set to None" (for
# example, explicitly clearing a document's category).
_UNSET: Final[object] = object()


@dataclass(frozen=True)
class VectorDocument:
    """A single unit of text indexed for semantic search.

    Attributes:
        id: A unique identifier for this document.
        text: The document's textual content.
        category: An optional category label used for filtering.
        tags: A tuple of normalized, lowercase tags used for
            filtering.
        metadata: A read-only mapping of arbitrary additional
            metadata associated with this document.
        created_at: The UTC timestamp at which this document was
            first indexed.
        updated_at: The UTC timestamp at which this document was most
            recently updated.
    """

    id: str
    text: str
    category: str | None
    tags: tuple[str, ...]
    metadata: Mapping[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SearchResult:
    """A single scored result returned from a search operation.

    Attributes:
        document: The matching document.
        similarity: A similarity score in the range ``[0.0, 1.0]``,
            where higher values indicate a closer match. Exact and
            partial text matches are scored ``1.0``.
    """

    document: VectorDocument
    similarity: float


def _validate_text(text: str) -> str:
    """Validate and normalize a text value.

    Args:
        text: The text to validate.

    Returns:
        The stripped text.

    Raises:
        MemoryError: If ``text`` is not a non-empty string.
    """
    if not isinstance(text, str) or not text.strip():
        raise MemoryError("Document text must be a non-empty string.")
    return text.strip()


def _validate_category(category: str | None) -> str | None:
    """Validate and normalize an optional category label.

    Args:
        category: The category to validate, or ``None``.

    Returns:
        The stripped, lowercased category, or ``None``.

    Raises:
        MemoryError: If ``category`` is provided but is not a
            non-empty string.
    """
    if category is None:
        return None
    if not isinstance(category, str) or not category.strip():
        raise MemoryError("Document category must be a non-empty string when provided.")
    return category.strip().lower()


def _validate_tags(tags: Sequence[str] | None) -> tuple[str, ...]:
    """Validate and normalize a sequence of tags.

    Args:
        tags: The tags to validate, or ``None``.

    Returns:
        A tuple of normalized, lowercase, de-duplicated tags. Empty if
        ``tags`` is ``None``.

    Raises:
        MemoryError: If any tag is not a non-empty string.
    """
    if tags is None:
        return ()

    normalized_tags: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        if not isinstance(tag, str) or not tag.strip():
            raise MemoryError("Document tags must be non-empty strings.")
        normalized_tag = tag.strip().lower()
        if normalized_tag not in seen:
            seen.add(normalized_tag)
            normalized_tags.append(normalized_tag)
    return tuple(normalized_tags)


def _validate_metadata(metadata: dict[str, Any] | None) -> Mapping[str, Any]:
    """Validate and normalize document metadata.

    Args:
        metadata: The metadata to validate, or ``None``.

    Returns:
        A read-only mapping of the provided metadata, or an empty
        read-only mapping if ``metadata`` is ``None``.

    Raises:
        MemoryError: If ``metadata`` is provided but is not a
            dictionary.
    """
    if metadata is None:
        return MappingProxyType({})
    if not isinstance(metadata, dict):
        raise MemoryError(
            f"Document metadata must be a dictionary, got {type(metadata).__name__}."
        )
    return MappingProxyType(dict(metadata))


def _validate_top_k(top_k: int) -> int:
    """Validate a top-k retrieval limit.

    Args:
        top_k: The limit to validate.

    Returns:
        The validated limit, unchanged.

    Raises:
        MemoryError: If ``top_k`` is not a positive integer.
    """
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
        raise MemoryError(f"top_k must be a positive integer, got {top_k!r}.")
    return top_k


def _validate_similarity_threshold(min_similarity: float) -> float:
    """Validate a minimum similarity threshold.

    Args:
        min_similarity: The threshold to validate.

    Returns:
        The validated threshold, unchanged.

    Raises:
        MemoryError: If ``min_similarity`` is not within
            ``[0.0, 1.0]``.
    """
    if not isinstance(min_similarity, (int, float)) or isinstance(min_similarity, bool):
        raise MemoryError(
            f"min_similarity must be a number, got {type(min_similarity).__name__}."
        )
    if not (_MIN_SIMILARITY <= min_similarity <= _MAX_SIMILARITY):
        raise MemoryError(
            f"min_similarity must be between {_MIN_SIMILARITY} and {_MAX_SIMILARITY} "
            f"inclusive, got {min_similarity}."
        )
    return float(min_similarity)


class VectorStore:
    """NOVA's local, in-memory semantic search layer.

    ``VectorStore`` indexes documents using a lightweight lexical
    term-frequency model and answers relevance-ranked queries against
    that index using cosine similarity. It is fully self-contained: it
    does not depend on any external service, database, or other NOVA
    subsystem.

    Attributes:
        _initialized: Whether the store is currently initialized and
            accepting operations.
        _lock: A reentrant lock guarding all internal state, making
            every public operation thread-safe.
        _documents: The primary store, mapping document ID to
            :class:`VectorDocument`.
        _term_frequencies: A mapping of document ID to that document's
            term-frequency vector, used internally for similarity
            scoring.
        _category_index: A mapping of normalized category to the set
            of document IDs belonging to that category.
        _tag_index: A mapping of normalized tag to the set of document
            IDs registered under that tag.
    """

    def __init__(self) -> None:
        """Construct an uninitialized vector store.

        The store must be initialized via :meth:`initialize` before
        any indexing or search operation is permitted.
        """
        self._initialized: bool = False
        self._lock: threading.RLock = threading.RLock()
        self._documents: dict[str, VectorDocument] = {}
        self._term_frequencies: dict[str, dict[str, float]] = {}
        self._category_index: dict[str, set[str]] = {}
        self._tag_index: dict[str, set[str]] = {}

    # -------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize the vector store, making it ready to serve requests.

        Calling this method more than once without an intervening
        :meth:`shutdown` is a no-op.
        """
        with self._lock:
            if self._initialized:
                logger.warning("VectorStore.initialize() called but already initialized.")
                return
            self._initialized = True
            logger.info("VectorStore initialized (backend='in_memory_term_frequency').")

    def shutdown(self) -> None:
        """Shut down the vector store.

        The in-memory index is preserved across shutdown; only the
        store's readiness flag is cleared. Calling this method when
        the store is not initialized is a no-op.
        """
        with self._lock:
            if not self._initialized:
                logger.warning("VectorStore.shutdown() called but not initialized.")
                return
            self._initialized = False
            logger.info("VectorStore shut down.")

    # -------------------------------------------------------------------
    # Indexing
    # -------------------------------------------------------------------

    def add_document(
        self,
        text: str,
        document_id: str | None = None,
        category: str | None = None,
        tags: Sequence[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> VectorDocument:
        """Index a new document for semantic search.

        Args:
            text: The document's textual content.
            document_id: An optional explicit identifier. If ``None``,
                a new identifier is generated automatically.
            category: An optional category label for filtering.
            tags: An optional sequence of tags for filtering.
            metadata: Optional arbitrary additional metadata.

        Returns:
            The newly indexed :class:`VectorDocument`.

        Raises:
            MemoryError: If the store is not initialized, if any
                argument fails validation, or if ``document_id`` is
                already in use.
        """
        with self._lock:
            self._ensure_initialized()
            normalized_text = _validate_text(text)
            normalized_category = _validate_category(category)
            normalized_tags = _validate_tags(tags)
            normalized_metadata = _validate_metadata(metadata)

            resolved_id = document_id if document_id is not None else uuid.uuid4().hex
            if resolved_id in self._documents:
                raise MemoryError(f"A document already exists with id '{resolved_id}'.")

            now = datetime.now(timezone.utc)
            document = VectorDocument(
                id=resolved_id,
                text=normalized_text,
                category=normalized_category,
                tags=normalized_tags,
                metadata=normalized_metadata,
                created_at=now,
                updated_at=now,
            )

            self._documents[resolved_id] = document
            self._term_frequencies[resolved_id] = self._compute_term_frequencies(normalized_text)
            self._index_document(document)

            logger.info(
                "Document indexed: id='%s', category='%s', tag_count=%d.",
                resolved_id,
                normalized_category,
                len(normalized_tags),
            )
            return document

    def update_document(
        self,
        document_id: str,
        *,
        text: Any = _UNSET,
        category: Any = _UNSET,
        tags: Any = _UNSET,
        metadata: Any = _UNSET,
    ) -> VectorDocument:
        """Update one or more fields of an existing indexed document.

        Only fields explicitly provided are changed. If ``text`` is
        changed, the document's term-frequency vector is recomputed.
        If ``category`` or ``tags`` are changed, the relevant indices
        are updated accordingly.

        Args:
            document_id: The unique ID of the document to update.
            text: The new text, if changing it.
            category: The new category, if changing it.
            tags: The new tags, if changing them.
            metadata: The new metadata, if changing it.

        Returns:
            The updated :class:`VectorDocument`.

        Raises:
            MemoryError: If the store is not initialized, if no
                document exists with ``document_id``, or if any
                provided field fails validation.
        """
        with self._lock:
            self._ensure_initialized()
            existing_document = self._documents.get(document_id)
            if existing_document is None:
                raise MemoryError(f"No document found with id '{document_id}'.")

            new_text = existing_document.text if text is _UNSET else _validate_text(text)
            new_category = (
                existing_document.category
                if category is _UNSET
                else _validate_category(category)
            )
            new_tags = existing_document.tags if tags is _UNSET else _validate_tags(tags)
            new_metadata = (
                existing_document.metadata if metadata is _UNSET else _validate_metadata(metadata)
            )

            updated_document = VectorDocument(
                id=existing_document.id,
                text=new_text,
                category=new_category,
                tags=new_tags,
                metadata=new_metadata,
                created_at=existing_document.created_at,
                updated_at=datetime.now(timezone.utc),
            )

            self._deindex_document(existing_document)
            self._documents[document_id] = updated_document
            self._term_frequencies[document_id] = self._compute_term_frequencies(new_text)
            self._index_document(updated_document)

            logger.info("Document '%s' updated.", document_id)
            return updated_document

    def remove_document(self, document_id: str) -> None:
        """Remove a document from the index.

        Args:
            document_id: The unique ID of the document to remove.

        Raises:
            MemoryError: If the store is not initialized, or if no
                document exists with ``document_id``.
        """
        with self._lock:
            self._ensure_initialized()
            document = self._documents.pop(document_id, None)
            if document is None:
                raise MemoryError(f"No document found with id '{document_id}'.")

            self._term_frequencies.pop(document_id, None)
            self._deindex_document(document)

            logger.info("Document '%s' removed from the index.", document_id)

    def remove_all(self) -> int:
        """Remove every document from the index.

        Returns:
            The number of documents that were removed.

        Raises:
            MemoryError: If the store is not initialized.
        """
        with self._lock:
            self._ensure_initialized()
            removed_count = len(self._documents)
            self._documents.clear()
            self._term_frequencies.clear()
            self._category_index.clear()
            self._tag_index.clear()

            logger.warning("Removed all %d documents from the index.", removed_count)
            return removed_count

    def contains(self, document_id: str) -> bool:
        """Check whether a document is currently indexed.

        Args:
            document_id: The unique ID to check.

        Returns:
            ``True`` if a document is indexed under ``document_id``,
            ``False`` otherwise.
        """
        with self._lock:
            return document_id in self._documents

    # -------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = _DEFAULT_TOP_K,
        min_similarity: float = _DEFAULT_MIN_SIMILARITY,
        category: str | None = None,
        tags: Sequence[str] | None = None,
        mode: SearchMode = "semantic",
    ) -> tuple[SearchResult, ...]:
        """Search indexed documents and return the most relevant matches.

        Args:
            query: The search query text.
            top_k: The maximum number of results to return.
            min_similarity: The minimum similarity score a result must
                meet to be included. Ignored for ``mode="exact"`` and
                ``mode="partial"``, which always score matches at
                ``1.0``.
            category: If provided, restricts the search to a single
                category.
            tags: If provided, restricts the search to documents with
                at least one matching tag.
            mode: ``"semantic"`` for term-frequency cosine similarity
                ranking, ``"exact"`` for exact full-text matches, or
                ``"partial"`` for substring matches.

        Returns:
            A tuple of :class:`SearchResult` instances, sorted by
            descending similarity, limited to ``top_k`` entries.

        Raises:
            MemoryError: If the store is not initialized, if any
                argument fails validation, or if ``mode`` is not
                recognized.
        """
        with self._lock:
            self._ensure_initialized()
            normalized_query = _validate_text(query)
            validated_top_k = _validate_top_k(top_k)
            validated_min_similarity = _validate_similarity_threshold(min_similarity)
            candidate_ids = self._filter_candidates(category, tags)

            results: list[SearchResult] = []
            if mode == "semantic":
                query_vector = self._compute_term_frequencies(normalized_query)
                for document_id in candidate_ids:
                    similarity = self._cosine_similarity(
                        query_vector, self._term_frequencies[document_id]
                    )
                    if similarity >= validated_min_similarity:
                        results.append(
                            SearchResult(document=self._documents[document_id], similarity=similarity)
                        )
            elif mode == "exact":
                normalized_query_lower = normalized_query.lower()
                for document_id in candidate_ids:
                    if self._documents[document_id].text.lower() == normalized_query_lower:
                        results.append(
                            SearchResult(document=self._documents[document_id], similarity=1.0)
                        )
            elif mode == "partial":
                normalized_query_lower = normalized_query.lower()
                for document_id in candidate_ids:
                    if normalized_query_lower in self._documents[document_id].text.lower():
                        results.append(
                            SearchResult(document=self._documents[document_id], similarity=1.0)
                        )
            else:
                raise MemoryError(f"Unknown search mode '{mode}'.")

            results.sort(key=lambda result: result.similarity, reverse=True)
            limited_results = tuple(results[:validated_top_k])
            logger.debug(
                "search() mode='%s' query='%s' returned %d result(s).",
                mode,
                normalized_query,
                len(limited_results),
            )
            return limited_results

    def search_by_category(
        self, category: str, top_k: int | None = None
    ) -> tuple[VectorDocument, ...]:
        """Retrieve documents belonging to a single category.

        Args:
            category: The category to retrieve documents for.
            top_k: If provided, limits the number of documents
                returned.

        Returns:
            A tuple of matching :class:`VectorDocument` instances.

        Raises:
            MemoryError: If the store is not initialized, or if
                ``category`` is not a non-empty string.
        """
        with self._lock:
            self._ensure_initialized()
            normalized_category = _validate_category(category)
            document_ids = self._category_index.get(normalized_category, set())
            documents = tuple(self._documents[document_id] for document_id in document_ids)
            if top_k is not None:
                documents = documents[: _validate_top_k(top_k)]
            return documents

    def search_by_tags(
        self,
        tags: Sequence[str],
        top_k: int | None = None,
        match_all: bool = False,
    ) -> tuple[VectorDocument, ...]:
        """Retrieve documents matching one or more tags.

        Args:
            tags: The tags to match against.
            top_k: If provided, limits the number of documents
                returned.
            match_all: If ``True``, a document must carry every tag in
                ``tags`` to match. If ``False`` (the default), a
                document matches if it carries at least one tag in
                ``tags``.

        Returns:
            A tuple of matching :class:`VectorDocument` instances.

        Raises:
            MemoryError: If the store is not initialized, or if any
                tag is not a non-empty string.
        """
        with self._lock:
            self._ensure_initialized()
            normalized_tags = _validate_tags(tags)
            if not normalized_tags:
                return ()

            tag_id_sets = [self._tag_index.get(tag, set()) for tag in normalized_tags]
            if match_all:
                matching_ids = set.intersection(*tag_id_sets) if tag_id_sets else set()
            else:
                matching_ids = set.union(*tag_id_sets) if tag_id_sets else set()

            documents = tuple(self._documents[document_id] for document_id in matching_ids)
            if top_k is not None:
                documents = documents[: _validate_top_k(top_k)]
            return documents

    def similar_documents(
        self,
        document_id: str,
        top_k: int = _DEFAULT_TOP_K,
        min_similarity: float = _DEFAULT_MIN_SIMILARITY,
    ) -> tuple[SearchResult, ...]:
        """Find documents most similar to an already-indexed document.

        Args:
            document_id: The unique ID of the reference document.
            top_k: The maximum number of results to return.
            min_similarity: The minimum similarity score a result must
                meet to be included.

        Returns:
            A tuple of :class:`SearchResult` instances, excluding the
            reference document itself, sorted by descending
            similarity, limited to ``top_k`` entries.

        Raises:
            MemoryError: If the store is not initialized, if no
                document exists with ``document_id``, or if any
                argument fails validation.
        """
        with self._lock:
            self._ensure_initialized()
            if document_id not in self._documents:
                raise MemoryError(f"No document found with id '{document_id}'.")

            validated_top_k = _validate_top_k(top_k)
            validated_min_similarity = _validate_similarity_threshold(min_similarity)
            reference_vector = self._term_frequencies[document_id]

            results: list[SearchResult] = []
            for candidate_id, candidate_vector in self._term_frequencies.items():
                if candidate_id == document_id:
                    continue
                similarity = self._cosine_similarity(reference_vector, candidate_vector)
                if similarity >= validated_min_similarity:
                    results.append(
                        SearchResult(document=self._documents[candidate_id], similarity=similarity)
                    )

            results.sort(key=lambda result: result.similarity, reverse=True)
            return tuple(results[:validated_top_k])

    # -------------------------------------------------------------------
    # Diagnostics
    # -------------------------------------------------------------------

    def statistics(self) -> dict[str, object]:
        """Return summary statistics about the current index.

        Returns:
            A dictionary containing the total number of indexed
            documents, per-category document counts, the total number
            of distinct tags, the size of the internal vocabulary, and
            the name of the active backend.
        """
        with self._lock:
            documents_per_category = {
                category: len(document_ids)
                for category, document_ids in self._category_index.items()
            }
            vocabulary: set[str] = set()
            for term_frequencies in self._term_frequencies.values():
                vocabulary.update(term_frequencies.keys())

            return {
                "total_documents": len(self._documents),
                "documents_per_category": documents_per_category,
                "total_tags": len(self._tag_index),
                "vocabulary_size": len(vocabulary),
                "backend": "in_memory_term_frequency",
            }

    def health_check(self) -> bool:
        """Verify that the vector store is initialized and internally consistent.

        Returns:
            ``True`` if the store is initialized and every document
            has a corresponding term-frequency vector, ``False``
            otherwise.
        """
        with self._lock:
            if not self._initialized:
                logger.warning("Health check failed: VectorStore is not initialized.")
                return False

            if set(self._documents.keys()) != set(self._term_frequencies.keys()):
                logger.error(
                    "Health check failed: document set does not match indexed "
                    "vector set."
                )
                return False

            logger.debug("VectorStore health check passed.")
            return True

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        """Verify the store is initialized before permitting an operation.

        Raises:
            MemoryError: If :meth:`initialize` has not been called
                successfully.
        """
        if not self._initialized:
            raise MemoryError("VectorStore is not initialized. Call initialize() first.")

    def _index_document(self, document: VectorDocument) -> None:
        """Add a document's ID to the category and tag indices.

        Args:
            document: The document to index.
        """
        if document.category is not None:
            self._category_index.setdefault(document.category, set()).add(document.id)
        for tag in document.tags:
            self._tag_index.setdefault(tag, set()).add(document.id)

    def _deindex_document(self, document: VectorDocument) -> None:
        """Remove a document's ID from the category and tag indices.

        Args:
            document: The document to remove from the indices.
        """
        if document.category is not None:
            self._category_index.get(document.category, set()).discard(document.id)
        for tag in document.tags:
            self._tag_index.get(tag, set()).discard(document.id)

    def _filter_candidates(
        self, category: str | None, tags: Sequence[str] | None
    ) -> set[str]:
        """Resolve the candidate document IDs for a search operation.

        Args:
            category: An optional category filter.
            tags: An optional tag filter; a document matches if it
                carries at least one of the given tags.

        Returns:
            The set of document IDs matching the given filters.

        Raises:
            MemoryError: If ``category`` is provided but is not a
                non-empty string, or if any tag is not a non-empty
                string.
        """
        if category is not None:
            normalized_category = _validate_category(category)
            candidate_ids = set(self._category_index.get(normalized_category, set()))
        else:
            candidate_ids = set(self._documents.keys())

        if tags:
            normalized_tags = _validate_tags(tags)
            tag_matches: set[str] = set()
            for tag in normalized_tags:
                tag_matches |= self._tag_index.get(tag, set())
            candidate_ids &= tag_matches

        return candidate_ids

    @staticmethod
    def _tokenize(text: str) -> tuple[str, ...]:
        """Tokenize text into lowercase alphanumeric tokens.

        Args:
            text: The text to tokenize.

        Returns:
            A tuple of lowercase tokens.
        """
        return tuple(_TOKEN_PATTERN.findall(text.lower()))

    @classmethod
    def _compute_term_frequencies(cls, text: str) -> dict[str, float]:
        """Compute a normalized term-frequency vector for a piece of text.

        This is the internal similarity representation used by the
        in-memory backend. A future embedding-backed implementation
        would replace this method (and :meth:`_cosine_similarity`)
        with a call to a real embedding model, without changing any
        public method signature.

        Args:
            text: The text to vectorize.

        Returns:
            A mapping of token to its normalized frequency within
            ``text``. Empty if ``text`` contains no recognizable
            tokens.
        """
        tokens = cls._tokenize(text)
        if not tokens:
            return {}

        raw_counts: dict[str, float] = {}
        for token in tokens:
            raw_counts[token] = raw_counts.get(token, 0.0) + 1.0

        total_tokens = float(len(tokens))
        return {token: count / total_tokens for token, count in raw_counts.items()}

    @staticmethod
    def _cosine_similarity(vector_a: dict[str, float], vector_b: dict[str, float]) -> float:
        """Compute the cosine similarity between two sparse term-frequency vectors.

        Args:
            vector_a: The first term-frequency vector.
            vector_b: The second term-frequency vector.

        Returns:
            The cosine similarity between the two vectors, in the
            range ``[0.0, 1.0]``. Returns ``0.0`` if either vector is
            empty.
        """
        if not vector_a or not vector_b:
            return 0.0

        shared_tokens = vector_a.keys() & vector_b.keys()
        dot_product = sum(vector_a[token] * vector_b[token] for token in shared_tokens)
        if dot_product == 0.0:
            return 0.0

        magnitude_a = math.sqrt(sum(value * value for value in vector_a.values()))
        magnitude_b = math.sqrt(sum(value * value for value in vector_b.values()))
        if magnitude_a == 0.0 or magnitude_b == 0.0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)


__all__ = [
    "VectorStore",
    "VectorDocument",
    "SearchResult",
]
