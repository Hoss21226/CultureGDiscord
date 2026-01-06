from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Question:
    category: str
    difficulty: str
    question: str
    choices: List[str]
    correct_index: int
    explanation : Optional[str] = None


