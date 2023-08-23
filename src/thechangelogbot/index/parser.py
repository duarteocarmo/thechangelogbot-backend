import pathlib
import re
from typing import Iterator, Optional

from loguru import logger
from thechangelogbot.index.snippet import Snippet


def filter_items(
    items: list[Snippet], num_words: int = 25
) -> Iterator[Snippet]:
    for snippet in items:
        if snippet.speaker == "Break":
            continue

        elif snippet.word_count < num_words:
            continue
        else:
            yield snippet


def parse_episode_text(
    episode_text: str,
    episode_number: int,
    podcast: str,
) -> list[Snippet]:
    text = ""
    speaking_items = []
    last_speaker = None

    for line in episode_text.splitlines():
        if not line:
            continue

        speaker_match = re.match(r"^\*\*(.+?):\*\*", line)

        if speaker_match:
            if last_speaker and text:
                speaking_items.append(
                    Snippet(
                        podcast=podcast,
                        episode_number=episode_number,
                        text=text.strip(),
                        speaker=last_speaker,
                    )
                )

            speaker = speaker_match.group(1)
            text = line.replace(f"**{speaker}:** ", "")
            last_speaker = speaker

        else:
            text += " " + line

    if last_speaker and text:
        speaking_items.append(
            Snippet(
                podcast=podcast,
                episode_number=episode_number,
                text=text.strip(),
                speaker=last_speaker,
            )
        )

    speaking_items = list(filter_items(speaking_items))

    return speaking_items


def process_podcast_directory(
    directory: pathlib.Path,
) -> Iterator[list[Snippet]]:
    for file in pathlib.Path(directory).iterdir():
        try:
            episode_number = int(file.stem.split("-")[-1])
            episode_text = file.read_text()

            yield parse_episode_text(
                episode_text=episode_text,
                episode_number=episode_number,
                podcast=directory.name,
            )

        except Exception as e:
            logger.error(f"Error processing {file.name}: {e}")


def index_snippets(
    transcript_repo_directory: str,
    podcast_filter: Optional[list[str]] = None,
    directories_to_ignore: list[str] = [".github", ".git", "scripts"],
) -> Iterator[Snippet]:
    for directory in pathlib.Path(transcript_repo_directory).iterdir():
        if not directory.is_dir() or directory.name in directories_to_ignore:
            continue

        if podcast_filter and directory.name not in podcast_filter:
            continue

        podcast = directory.name
        logger.info(f"Processing podcast {podcast}...")

        for items in list(process_podcast_directory(directory=directory)):
            yield from items
