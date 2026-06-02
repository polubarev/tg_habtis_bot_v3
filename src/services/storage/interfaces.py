
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from src.models.entry import HabitEntry, DreamEntry, ThoughtEntry, ReflectionEntry
from src.models.user import UserProfile


class IUserRepository(ABC):
    """Interface for user data persistence."""

    @abstractmethod
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserProfile]:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> list[UserProfile]:
        raise NotImplementedError

    @abstractmethod
    async def create(self, user: UserProfile) -> UserProfile:
        raise NotImplementedError

    @abstractmethod
    async def update(self, user: UserProfile) -> UserProfile:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, telegram_id: int) -> bool:
        raise NotImplementedError


class ISessionRepository(ABC):
    """Interface for conversation session storage."""

    @abstractmethod
    async def get(self, user_id: int):
        raise NotImplementedError

    @abstractmethod
    async def save(self, session) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, user_id: int) -> None:
        raise NotImplementedError


@dataclass
class HabitRowLookup:
    row_index: int
    raw_record: str
    entry_data: dict[str, Any] | None = None


class ISheetsClient(ABC):
    """Interface for working with Google Sheets."""

    @abstractmethod
    async def append_habit_entry(self, sheet_id: str, field_order: list[str], entry: HabitEntry) -> None:
        raise NotImplementedError

    @abstractmethod
    async def append_dream_entry(self, sheet_id: str, entry: DreamEntry) -> None:
        raise NotImplementedError

    @abstractmethod
    async def append_thought_entry(self, sheet_id: str, entry: ThoughtEntry) -> None:
        raise NotImplementedError

    @abstractmethod
    async def append_reflection_entry(self, sheet_id: str, entry: ReflectionEntry) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_latest_habit_entry(
        self,
        sheet_id: str,
        entry_date: date,
    ) -> Optional[HabitRowLookup]:
        raise NotImplementedError

    @abstractmethod
    async def update_habit_entry(
        self,
        sheet_id: str,
        row_index: int,
        field_order: list[str],
        entry: HabitEntry,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_habit_entries_for_dates(
        self,
        sheet_id: str,
        dates: list[date],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_dream_entries_for_dates(
        self,
        sheet_id: str,
        dates: list[date],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_thought_entries_for_dates(
        self,
        sheet_id: str,
        dates: list[date],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_reflection_entries_for_dates(
        self,
        sheet_id: str,
        dates: list[date],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def ensure_tabs(self, sheet_id: str) -> None:
        raise NotImplementedError
