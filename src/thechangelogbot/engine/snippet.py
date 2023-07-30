import re
from dataclasses import dataclass, field
from hashlib import md5
from typing import Optional

import numpy as np


def clean_text(text: str) -> str:
    text = re.sub(r"\\\[\d{1,2}:\d{1,2}\\\]\s", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


@dataclass
class Snippet:
    podcast_name: str
    episode_number: int
    text: str
    speaker: str
    id: str = field(init=False)
    num_words: int = field(init=False)
    embedding: Optional[np.ndarray] = field(init=False, default=None)

    def __post_init__(self):
        self.id = md5(
            f"{self.podcast_name}{self.episode_number}{self.text}{self.speaker}".encode(
                "utf-8"
            )
        ).hexdigest()

        self.text = clean_text(self.text)
        self.num_words = len(self.text.split())
