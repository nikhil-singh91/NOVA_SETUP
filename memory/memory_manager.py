"""Central persistent memory system for NOVA.

This module implements :class:`MemoryManager`, the component
responsible for storing, retrieving, searching, and permanently
retaining everything NOVA is told to remember: user profile facts,
preferences, projects, tasks, reminders, notes, goals, conversation
context, and any other category of information. Unless a memory is
explicitly deleted, NOVA never forgets it.

Storage:
    Memories are persisted as JSON on disk, under
    :data:`~core.paths.MEMORY_DIR`, and are loaded into memory once at
    startup. Every write is performed atomically (write to a temporary
    file in the same directory, then replace the target file), so a
    crash or power loss mid-write can never corrupt the store. If the
    store on disk is found to be corrupted at load time, it is
    quarantined (renamed aside with a timestamp) and NOVA starts with
    a fresh, empty store rather than crashing.

Future Compatibility:
    ``MemoryManager``'s public API is intentionally storage-agnostic:
    every method operates in terms of :class:`MemoryEntry` objects,
    never in terms of JSON, file paths, or on-disk structure. A future
    vector-database-backed implementation (for semantic search) can
    be introduced by changing only the private persistence methods
    (:meth:`MemoryManager._load`, :meth:`MemoryManager._save`) or by
    composing a separate ``vector_store`` module that indexes entries
    already flowing through this manager's public API, without any
    change to how other NOVA modules (``system_prompt``, voice
    modules, ``main.py``, and so on) call into memory.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Final, Sequence

# from core.exceptions import MemorySystemError
from core.exceptions import MemorySystemError as MemoryError
from core.logger import get_logger
from core.paths import MEMORY_DIR

logger = get_logger(__name__)

_DEFAULT_STORAGE_FILENAME: Final[str] = "memory_store.json"
_MIN_IMPORTANCE: Final[int] = 1
_MAX_IMPORTANCE: Final[int] = 5
_DEFAULT_IMPORTANCE: Final[int] = 3

# A sentinel used by update_memory to distinguish "this field was not
# provided" from "this field was explicitly set to None". Using None
# itself as the default would make it impossible to intentionally
# clear a field to None.
_UNSET: Final[object] = object()


class MemoryCategory(str, Enum):
    """The categories of information NOVA's memory system can store.

    Attributes:
        PROFILE: Facts about the user's identity and life.
        PREFERENCES: The user's stated likes, dislikes, and settings.
        PROJECTS: Information about ongoing projects.
        CODING: Coding-related facts, conventions, and context.
        EDUCATION: Educational background and learning goals.
        TASKS: Actionable to-do items.
        REMINDERS: Time- or event-based reminders.
        CONVERSATIONS: Retained context from past conversations.
        NOTES: Freeform notes that do not fit another category.
        GOALS: Long-term goals and aspirations.
        AI_SETTINGS: User preferences about NOVA's own behavior.
        CUSTOM: Any category not covered above.
    """

    PROFILE = "profile"
    PREFERENCES = "preferences"
    PROJECTS = "projects"
    CODING = "coding"
    EDUCATION = "education"
    TASKS = "tasks"
    REMINDERS = "reminders"
    CONVERSATIONS = "conversations"
    NOTES = "notes"
    GOALS = "goals"
    AI_SETTINGS = "ai_settings"
    CUSTOM = "custom"


@dataclass(frozen=True)
class MemoryEntry:
    """A single, immutable unit of information stored in NOVA's memory.

    Instances are never mutated in place; :meth:`MemoryManager.update_memory`
    produces a new ``MemoryEntry`` with an updated ``updated_at``
    timestamp rather than modifying an existing one. This makes it
    safe to hand out ``MemoryEntry`` instances to callers without
    risk of them being changed underneath the manager.

    Attributes:
        id: A unique identifier for this memory entry.
        category: The :class:`MemoryCategory` this entry belongs to.
        key: A short, descriptive label for this memory (for example,
            ``"favorite_editor"``).
        value: The remembered value itself. Must be JSON-serializable
            for persistence to succeed.
        importance: An integer importance rating, from
            :data:`_MIN_IMPORTANCE` to :data:`_MAX_IMPORTANCE`
            inclusive, where higher means more important.
        tags: A tuple of normalized, lowercase tags associated with
            this entry, used for search and filtering.
        created_at: The UTC timestamp at which this entry was first
            created.
        updated_at: The UTC timestamp at which this entry was most
            recently updated.
    """

    id: str
    category: MemoryCategory
    key: str
    value: Any
    importance: int
    tags: tuple[str, ...]
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Serialize this entry into a JSON-compatible dictionary.

        Returns:
            A dictionary representation suitable for ``json.dump``.
        """
        return {
            "id": self.id,
            "category": self.category.value,
            "key": self.key,
            "value": self.value,
            "importance": self.importance,
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        """Deserialize a ``MemoryEntry`` from a stored dictionary.

        Args:
            data: A dictionary previously produced by :meth:`to_dict`,
                or loaded from disk.

        Returns:
            The reconstructed ``MemoryEntry``.

        Raises:
            MemoryError: If ``data`` is missing required fields or
                contains values that cannot be parsed into a valid
                entry.
        """
        try:
            return cls(
                id=str(data["id"]),
                category=MemoryCategory(str(data["category"])),
                key=str(data["key"]),
                value=data["value"],
                importance=int(data["importance"]),
                tags=tuple(str(tag) for tag in data.get("tags", [])),
                created_at=datetime.fromisoformat(str(data["created_at"])),
                updated_at=datetime.fromisoformat(str(data["updated_at"])),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise MemoryError(
                f"Failed to parse a stored memory entry: {exc}", original_exception=exc
            ) from exc


def _validate_category(category: MemoryCategory | str) -> MemoryCategory:
    """Validate and normalize a memory category.

    Args:
        category: A :class:`MemoryCategory` member, or its string
            value.

    Returns:
        The corresponding :class:`MemoryCategory` member.

    Raises:
        MemoryError: If ``category`` does not correspond to any known
            :class:`MemoryCategory` value.
    """
    if isinstance(category, MemoryCategory):
        return category
    try:
        return MemoryCategory(str(category).strip().lower())
    except ValueError as exc:
        valid_categories = ", ".join(sorted(member.value for member in MemoryCategory))
        raise MemoryError(
            f"Invalid memory category '{category}'. Valid categories are: "
            f"{valid_categories}.",
            original_exception=exc,
        ) from exc


def _validate_key(key: str) -> str:
    """Validate and normalize a memory key.

    Args:
        key: The key to validate.

    Returns:
        The stripped key.

    Raises:
        MemoryError: If ``key`` is not a non-empty string.
    """
    if not isinstance(key, str) or not key.strip():
        raise MemoryError("Memory key must be a non-empty string.")
    return key.strip()


def _validate_importance(importance: int) -> int:
    """Validate a memory importance rating.

    Args:
        importance: The importance value to validate.

    Returns:
        The validated importance value, unchanged.

    Raises:
        MemoryError: If ``importance`` is not an integer within the
            supported range.
    """
    if not isinstance(importance, int) or isinstance(importance, bool):
        raise MemoryError(
            f"Memory importance must be an integer, got {type(importance).__name__}."
        )
    if not (_MIN_IMPORTANCE <= importance <= _MAX_IMPORTANCE):
        raise MemoryError(
            f"Memory importance must be between {_MIN_IMPORTANCE} and "
            f"{_MAX_IMPORTANCE} inclusive, got {importance}."
        )
    return importance


def _validate_tags(tags: Sequence[str] | None) -> tuple[str, ...]:
    """Validate and normalize a sequence of memory tags.

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
            raise MemoryError("Memory tags must be non-empty strings.")
        normalized_tag = tag.strip().lower()
        if normalized_tag not in seen:
            seen.add(normalized_tag)
            normalized_tags.append(normalized_tag)
    return tuple(normalized_tags)


class MemoryManager:
    """NOVA's central, persistent, thread-safe memory system.

    ``MemoryManager`` stores every memory entry in an in-memory
    dictionary keyed by entry ID for O(1) lookup, maintains secondary
    indices (by category and by normalized key) for O(1) filtering,
    and persists the full store to disk as JSON after every
    modification using atomic writes.

    Attributes:
        _storage_path: The path to the JSON file used to persist
            memory entries.
        _lock: A reentrant lock guarding all internal state, making
            every public operation thread-safe.
        _memories: The primary store, mapping entry ID to
            :class:`MemoryEntry`.
        _category_index: A mapping of :class:`MemoryCategory` to the
            set of entry IDs belonging to that category.
        _key_index: A mapping of normalized (stripped, lowercased) key
            to the set of entry IDs registered under that key.
    """

    def __init__(self, storage_path: Path | None = None) -> None:
        """Initialize the memory manager and load any existing store.

        Args:
            storage_path: The JSON file to persist memories to. If
                ``None``, defaults to a file named
                :data:`_DEFAULT_STORAGE_FILENAME` under
                :data:`~core.paths.MEMORY_DIR`.
        """
        self._storage_path: Path = (
            storage_path if storage_path is not None else MEMORY_DIR / _DEFAULT_STORAGE_FILENAME
        )
        self._lock: threading.RLock = threading.RLock()
        self._memories: dict[str, MemoryEntry] = {}
        self._category_index: dict[MemoryCategory, set[str]] = {
            category: set() for category in MemoryCategory
        }
        self._key_index: dict[str, set[str]] = {}

        self._load()

    # -------------------------------------------------------------------
    # Public API: mutation
    # -------------------------------------------------------------------

    def add_memory(
        self,
        category: MemoryCategory | str,
        key: str,
        value: Any,
        importance: int = _DEFAULT_IMPORTANCE,
        tags: Sequence[str] | None = None,
    ) -> MemoryEntry:
        """Add a new memory entry.

        Args:
            category: The category this memory belongs to.
            key: A short, descriptive label for this memory.
            value: The value to remember. Must be JSON-serializable.
            importance: An importance rating between
                :data:`_MIN_IMPORTANCE` and :data:`_MAX_IMPORTANCE`
                inclusive. Defaults to :data:`_DEFAULT_IMPORTANCE`.
            tags: An optional sequence of tags for search and
                filtering.

        Returns:
            The newly created :class:`MemoryEntry`.

        Raises:
            MemoryError: If any argument fails validation, or if the
                updated store cannot be persisted to disk.
        """
        with self._lock:
            normalized_category = _validate_category(category)
            normalized_key = _validate_key(key)
            normalized_importance = _validate_importance(importance)
            normalized_tags = _validate_tags(tags)

            now = datetime.now(timezone.utc)
            entry = MemoryEntry(
                id=uuid.uuid4().hex,
                category=normalized_category,
                key=normalized_key,
                value=value,
                importance=normalized_importance,
                tags=normalized_tags,
                created_at=now,
                updated_at=now,
            )

            self._memories[entry.id] = entry
            self._category_index[normalized_category].add(entry.id)
            self._key_index.setdefault(self._normalize_key(normalized_key), set()).add(entry.id)

            self._save()
            logger.info(
                "Memory added: id='%s', category='%s', key='%s'.",
                entry.id,
                normalized_category.value,
                normalized_key,
            )
            return entry

    def update_memory(
        self,
        memory_id: str,
        *,
        key: Any = _UNSET,
        value: Any = _UNSET,
        category: Any = _UNSET,
        importance: Any = _UNSET,
        tags: Any = _UNSET,
    ) -> MemoryEntry:
        """Update one or more fields of an existing memory entry.

        Only fields explicitly provided are changed; any field left
        at its default is preserved unchanged. Because entries are
        immutable, this replaces the stored entry with a new instance
        carrying an updated ``updated_at`` timestamp.

        Args:
            memory_id: The unique ID of the memory entry to update.
            key: The new key, if changing it.
            value: The new value, if changing it.
            category: The new category, if changing it.
            importance: The new importance rating, if changing it.
            tags: The new tags, if changing them.

        Returns:
            The updated :class:`MemoryEntry`.

        Raises:
            MemoryError: If no entry exists with ``memory_id``, if any
                provided field fails validation, or if the updated
                store cannot be persisted to disk.
        """
        with self._lock:
            existing_entry = self._memories.get(memory_id)
            if existing_entry is None:
                raise MemoryError(f"No memory entry found with id '{memory_id}'.")

            old_category = existing_entry.category
            old_normalized_key = self._normalize_key(existing_entry.key)

            new_key = existing_entry.key if key is _UNSET else _validate_key(key)
            new_value = existing_entry.value if value is _UNSET else value
            new_category = (
                existing_entry.category if category is _UNSET else _validate_category(category)
            )
            new_importance = (
                existing_entry.importance
                if importance is _UNSET
                else _validate_importance(importance)
            )
            new_tags = existing_entry.tags if tags is _UNSET else _validate_tags(tags)

            updated_entry = MemoryEntry(
                id=existing_entry.id,
                category=new_category,
                key=new_key,
                value=new_value,
                importance=new_importance,
                tags=new_tags,
                created_at=existing_entry.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            self._memories[memory_id] = updated_entry

            if new_category != old_category:
                self._category_index[old_category].discard(memory_id)
                self._category_index[new_category].add(memory_id)

            new_normalized_key = self._normalize_key(new_key)
            if new_normalized_key != old_normalized_key:
                self._key_index.get(old_normalized_key, set()).discard(memory_id)
                self._key_index.setdefault(new_normalized_key, set()).add(memory_id)

            self._save()
            logger.info("Memory '%s' updated.", memory_id)
            return updated_entry

    def delete_memory(self, memory_id: str) -> None:
        """Permanently delete a memory entry.

        Args:
            memory_id: The unique ID of the memory entry to delete.

        Raises:
            MemoryError: If no entry exists with ``memory_id``, or if
                the updated store cannot be persisted to disk.
        """
        with self._lock:
            entry = self._memories.pop(memory_id, None)
            if entry is None:
                raise MemoryError(f"No memory entry found with id '{memory_id}'.")

            self._category_index[entry.category].discard(memory_id)
            self._key_index.get(self._normalize_key(entry.key), set()).discard(memory_id)

            self._save()
            logger.info("Memory '%s' deleted.", memory_id)

    def clear_category(self, category: MemoryCategory | str) -> int:
        """Delete every memory entry belonging to a category.

        Args:
            category: The category to clear.

        Returns:
            The number of memory entries that were removed.

        Raises:
            MemoryError: If ``category`` is not a valid category, or
                if the updated store cannot be persisted to disk.
        """
        with self._lock:
            normalized_category = _validate_category(category)
            entry_ids = tuple(self._category_index.get(normalized_category, set()))

            for memory_id in entry_ids:
                entry = self._memories.pop(memory_id, None)
                if entry is not None:
                    self._key_index.get(self._normalize_key(entry.key), set()).discard(memory_id)

            self._category_index[normalized_category].clear()
            self._save()
            logger.warning(
                "Cleared %d memory entries from category '%s'.",
                len(entry_ids),
                normalized_category.value,
            )
            return len(entry_ids)

    def clear_all(self) -> int:
        """Delete every memory entry across all categories.

        Returns:
            The number of memory entries that were removed.

        Raises:
            MemoryError: If the updated (now empty) store cannot be
                persisted to disk.
        """
        with self._lock:
            removed_count = len(self._memories)
            self._memories.clear()
            for id_set in self._category_index.values():
                id_set.clear()
            self._key_index.clear()

            self._save()
            logger.warning("Cleared all %d memory entries.", removed_count)
            return removed_count

    # -------------------------------------------------------------------
    # Public API: retrieval
    # -------------------------------------------------------------------

    def get_memory(self, memory_id: str) -> MemoryEntry:
        """Retrieve a single memory entry by its unique ID.

        Args:
            memory_id: The unique ID of the memory entry to retrieve.

        Returns:
            The matching :class:`MemoryEntry`.

        Raises:
            MemoryError: If no entry exists with ``memory_id``.
        """
        with self._lock:
            entry = self._memories.get(memory_id)
            if entry is None:
                raise MemoryError(f"No memory entry found with id '{memory_id}'.")
            return entry

    def get_by_category(self, category: MemoryCategory | str) -> tuple[MemoryEntry, ...]:
        """Retrieve every memory entry belonging to a category.

        Args:
            category: The category to retrieve entries for.

        Returns:
            A tuple of matching :class:`MemoryEntry` instances.

        Raises:
            MemoryError: If ``category`` is not a valid category.
        """
        with self._lock:
            normalized_category = _validate_category(category)
            entry_ids = self._category_index.get(normalized_category, set())
            return tuple(self._memories[memory_id] for memory_id in entry_ids)

    def list_memories(
        self, category: MemoryCategory | str | None = None
    ) -> tuple[MemoryEntry, ...]:
        """List every memory entry, optionally filtered by category.

        Args:
            category: If provided, only entries in this category are
                returned. If ``None``, every entry is returned.

        Returns:
            A tuple of matching :class:`MemoryEntry` instances.

        Raises:
            MemoryError: If ``category`` is provided but is not a
                valid category.
        """
        with self._lock:
            if category is None:
                return tuple(self._memories.values())
            return self.get_by_category(category)

    def memory_exists(self, memory_id: str) -> bool:
        """Check whether a memory entry exists.

        Args:
            memory_id: The unique ID to check.

        Returns:
            ``True`` if an entry exists with ``memory_id``, ``False``
            otherwise.
        """
        with self._lock:
            return memory_id in self._memories

    def search_memory(
        self,
        query: str | None = None,
        category: MemoryCategory | str | None = None,
        tags: Sequence[str] | None = None,
        min_importance: int | None = None,
        max_importance: int | None = None,
        exact_key: bool = False,
    ) -> tuple[MemoryEntry, ...]:
        """Search memory entries using one or more combined filters.

        Args:
            query: If provided, matches entries whose key contains
                this text (or, if ``exact_key`` is ``True``, whose key
                exactly equals this text after normalization), or
                whose value contains this text.
            category: If provided, restricts the search to a single
                category.
            tags: If provided, restricts the search to entries with at
                least one matching tag.
            min_importance: If provided, excludes entries with a lower
                importance rating.
            max_importance: If provided, excludes entries with a
                higher importance rating.
            exact_key: If ``True``, ``query`` is matched as an exact,
                normalized key rather than a substring.

        Returns:
            A tuple of matching :class:`MemoryEntry` instances.

        Raises:
            MemoryError: If ``category`` is provided but is not a
                valid category.
        """
        with self._lock:
            if category is not None:
                normalized_category = _validate_category(category)
                candidate_ids: set[str] = set(
                    self._category_index.get(normalized_category, set())
                )
            else:
                candidate_ids = set(self._memories.keys())

            if query:
                normalized_query = query.strip().lower()
                if exact_key:
                    candidate_ids &= self._key_index.get(normalized_query, set())
                else:
                    candidate_ids = {
                        memory_id
                        for memory_id in candidate_ids
                        if self._matches_text_query(self._memories[memory_id], normalized_query)
                    }

            if tags:
                normalized_tags = {tag.strip().lower() for tag in tags if tag.strip()}
                candidate_ids = {
                    memory_id
                    for memory_id in candidate_ids
                    if normalized_tags & set(self._memories[memory_id].tags)
                }

            if min_importance is not None:
                candidate_ids = {
                    memory_id
                    for memory_id in candidate_ids
                    if self._memories[memory_id].importance >= min_importance
                }

            if max_importance is not None:
                candidate_ids = {
                    memory_id
                    for memory_id in candidate_ids
                    if self._memories[memory_id].importance <= max_importance
                }

            results = tuple(self._memories[memory_id] for memory_id in candidate_ids)
            logger.debug("search_memory returned %d result(s).", len(results))
            return results

    # -------------------------------------------------------------------
    # Public API: import / export
    # -------------------------------------------------------------------

    def export_memory(self, export_path: Path) -> int:
        """Export every memory entry to a JSON file.

        Args:
            export_path: The file to write the export to.

        Returns:
            The number of memory entries exported.

        Raises:
            MemoryError: If the export file cannot be written.
        """
        with self._lock:
            payload = {"memories": [entry.to_dict() for entry in self._memories.values()]}
            self._atomic_write(export_path, payload)
            logger.info(
                "Exported %d memory entries to '%s'.", len(self._memories), export_path
            )
            return len(self._memories)

    def import_memory(self, import_path: Path, *, merge: bool = True) -> int:
        """Import memory entries from a JSON file.

        Args:
            import_path: The file to import entries from. Must be in
                the format produced by :meth:`export_memory`.
            merge: If ``True``, imported entries are merged into the
                existing store (overwriting any entry with the same
                ID). If ``False``, the existing store is cleared
                first.

        Returns:
            The number of memory entries successfully imported. Any
            individual malformed entry is skipped and logged rather
            than aborting the entire import.

        Raises:
            MemoryError: If ``import_path`` cannot be read or does not
                contain valid JSON, or if the updated store cannot be
                persisted to disk.
        """
        with self._lock:
            try:
                raw_text = import_path.read_text(encoding="utf-8")
                payload = json.loads(raw_text)
            except (OSError, json.JSONDecodeError) as exc:
                raise MemoryError(
                    f"Failed to read import file '{import_path}': {exc}",
                    original_exception=exc,
                ) from exc

            if not merge:
                self._memories.clear()
                for id_set in self._category_index.values():
                    id_set.clear()
                self._key_index.clear()

            imported_count = 0
            for entry_data in payload.get("memories", []):
                try:
                    entry = MemoryEntry.from_dict(entry_data)
                except MemoryError as exc:
                    logger.warning("Skipping invalid memory entry during import: %s", exc)
                    continue

                self._memories[entry.id] = entry
                self._category_index[entry.category].add(entry.id)
                self._key_index.setdefault(self._normalize_key(entry.key), set()).add(entry.id)
                imported_count += 1

            self._save()
            logger.info(
                "Imported %d memory entries from '%s' (merge=%s).",
                imported_count,
                import_path,
                merge,
            )
            return imported_count

    # -------------------------------------------------------------------
    # Public API: diagnostics
    # -------------------------------------------------------------------

    def health_check(self) -> bool:
        """Verify that the memory store is internally consistent and writable.

        Checks that the category index accounts for exactly as many
        entries as the primary store, and performs a trial write to
        the storage directory to confirm it remains writable.

        Returns:
            ``True`` if the memory store is healthy, ``False``
            otherwise.
        """
        with self._lock:
            indexed_total = sum(len(ids) for ids in self._category_index.values())
            if indexed_total != len(self._memories):
                logger.error(
                    "Health check failed: category index count (%d) does not "
                    "match memory count (%d).",
                    indexed_total,
                    len(self._memories),
                )
                return False

            probe_path = self._storage_path.parent / f".health_check_{uuid.uuid4().hex}.tmp"
            try:
                self._storage_path.parent.mkdir(parents=True, exist_ok=True)
                probe_path.write_text("ok", encoding="utf-8")
                probe_path.unlink()
            except OSError as exc:
                logger.error(
                    "Health check failed: storage directory is not writable: %s",
                    exc,
                    exc_info=True,
                )
                return False

            logger.debug("Memory manager health check passed.")
            return True

    def statistics(self) -> dict[str, object]:
        """Return summary statistics about the current memory store.

        Returns:
            A dictionary containing the total number of memories,
            per-category counts, average importance, the storage file
            path, and the storage file's size in bytes.
        """
        with self._lock:
            total_memories = len(self._memories)
            memories_per_category = {
                category.value: len(ids) for category, ids in self._category_index.items()
            }
            importances = [entry.importance for entry in self._memories.values()]
            average_importance = sum(importances) / total_memories if total_memories else 0.0
            storage_size_bytes = (
                self._storage_path.stat().st_size if self._storage_path.exists() else 0
            )

            return {
                "total_memories": total_memories,
                "memories_per_category": memories_per_category,
                "average_importance": average_importance,
                "storage_path": str(self._storage_path),
                "storage_size_bytes": storage_size_bytes,
            }

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _normalize_key(key: str) -> str:
        """Normalize a key for use in the exact-key search index.

        Args:
            key: The key to normalize.

        Returns:
            The stripped, lowercased key.
        """
        return key.strip().lower()

    @staticmethod
    def _matches_text_query(entry: MemoryEntry, normalized_query: str) -> bool:
        """Check whether an entry's key or value contains a search query.

        Args:
            entry: The entry to check.
            normalized_query: The already-lowercased, stripped query
                text.

        Returns:
            ``True`` if ``normalized_query`` appears in the entry's
            key or in the string representation of its value.
        """
        if normalized_query in entry.key.lower():
            return True
        return normalized_query in str(entry.value).lower()

    def _load(self) -> None:
        """Load the memory store from disk, recovering from corruption.

        If the storage file does not exist, an empty store is created
        and immediately persisted. If the storage file exists but
        cannot be parsed, it is quarantined (renamed aside) and NOVA
        starts with a fresh, empty store rather than crashing.
        """
        with self._lock:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)

            if not self._storage_path.exists():
                logger.info(
                    "No existing memory store found at '%s'; creating a new one.",
                    self._storage_path,
                )
                self._save()
                return

            try:
                raw_text = self._storage_path.read_text(encoding="utf-8")
                payload = json.loads(raw_text)
            except (OSError, json.JSONDecodeError) as exc:
                logger.error(
                    "Memory store at '%s' is corrupted or unreadable: %s. "
                    "Recovering with a fresh store.",
                    self._storage_path,
                    exc,
                    exc_info=True,
                )
                self._quarantine_corrupted_store()
                self._save()
                return

            loaded_count = 0
            for entry_data in payload.get("memories", []):
                try:
                    entry = MemoryEntry.from_dict(entry_data)
                except MemoryError as exc:
                    logger.warning("Skipping corrupted memory entry during load: %s", exc)
                    continue

                self._memories[entry.id] = entry
                self._category_index[entry.category].add(entry.id)
                self._key_index.setdefault(self._normalize_key(entry.key), set()).add(entry.id)
                loaded_count += 1

            logger.info(
                "Loaded %d memory entries from '%s'.", loaded_count, self._storage_path
            )

    def _quarantine_corrupted_store(self) -> None:
        """Rename a corrupted storage file aside so it is not lost or reused.

        The quarantined file is kept alongside the active store, with
        a UTC timestamp in its name, so a corrupted store can still be
        inspected or manually recovered later.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        quarantine_path = self._storage_path.with_name(
            f"{self._storage_path.stem}.corrupted-{timestamp}{self._storage_path.suffix}"
        )
        try:
            self._storage_path.rename(quarantine_path)
            logger.warning("Corrupted memory store quarantined at '%s'.", quarantine_path)
        except OSError as exc:
            logger.error(
                "Failed to quarantine corrupted memory store at '%s': %s",
                self._storage_path,
                exc,
                exc_info=True,
            )

    def _save(self) -> None:
        """Persist the current in-memory store to disk atomically."""
        with self._lock:
            payload = {"memories": [entry.to_dict() for entry in self._memories.values()]}
            self._atomic_write(self._storage_path, payload)
            logger.debug(
                "Memory store saved to '%s' (%d entries).",
                self._storage_path,
                len(self._memories),
            )

    @staticmethod
    def _atomic_write(target_path: Path, payload: dict[str, Any]) -> None:
        """Write a JSON payload to a file atomically.

        The payload is first written to a temporary file in the same
        directory as ``target_path``, flushed and fsynced to disk, and
        only then moved into place over ``target_path``. This ensures
        ``target_path`` is never left in a partially written state,
        even if the process is interrupted mid-write.

        Args:
            target_path: The file to write the payload to.
            payload: The JSON-serializable payload to write.

        Raises:
            MemoryError: If the file cannot be written or moved into
                place.
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target_path.parent,
                prefix=f".{target_path.stem}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                json.dump(payload, temp_file, indent=2, ensure_ascii=False, default=str)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_path = Path(temp_file.name)
            temp_path.replace(target_path)
        except OSError as exc:
            raise MemoryError(
                f"Failed to write memory store to '{target_path}': {exc}",
                original_exception=exc,
            ) from exc


__all__ = [
    "MemoryCategory",
    "MemoryEntry",
    "MemoryManager",
]
