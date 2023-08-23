import re
from dataclasses import dataclass
from hashlib import md5


def clean_text(text: str) -> str:
    text = re.sub(r"\\\[\d{1,2}:\d{1,2}\\\]\s", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


@dataclass
class Snippet:
    podcast: str
    episode_number: int
    text: str
    speaker: str
    _hash: str = ""
    word_count: int = 0

    def __post_init__(self):
        to_encode = (
            f"{self.podcast}{self.episode_number}{self.text}{self.speaker}"
        )
        self._hash = str(md5(to_encode.encode("UTF-8")).hexdigest())
        self.text = clean_text(self.text)
        self.word_count = len(self.text.split())
