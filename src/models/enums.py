from enum import Enum


class Language(str, Enum):
    RU = "ru"
    EN = "en"


class InputType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    MIXED = "mixed"


class EntryType(str, Enum):
    HABIT = "habit"
    DREAM = "dream"
    THOUGHT = "thought"
    REFLECTION = "reflection"
