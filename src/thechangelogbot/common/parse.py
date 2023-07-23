import pathlib
import re

from git import Repo


def parse_episode_text(
    episode_text: str,
) -> tuple[list[tuple[str, str]], list[str]]:
    text = ""
    speaking_items = []
    last_speaker = None

    for line in episode_text.splitlines():
        if not line:
            continue

        speaker_match = re.match(r"^\*\*(.+?):\*\*", line)

        if speaker_match:
            if last_speaker and text:
                speaking_items.append((last_speaker, text.strip()))

            speaker = speaker_match.group(1)
            text = line.replace(f"**{speaker}:** ", "")
            last_speaker = speaker

        else:
            text += " " + line

    if last_speaker and text:
        speaking_items.append((last_speaker, text.strip()))

    speaking_items = filter_items(speaking_items)
    speakers = list(set([s for s, _ in speaking_items]))

    return speaking_items, speakers


def clean_text(text: str) -> str:
    text = re.sub(r"\\\[\d{1,2}:\d{1,2}\\\]\s", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def filter_items(
    items: list[tuple[str, str]], num_words: int = 15
) -> list[tuple[str, str]]:
    items = [(s, t) for s, t in items if s != "Break"]
    items = [(s, clean_text(t)) for s, t in items]
    items = [(s, t) for s, t in items if len(t.split()) > num_words]

    return items


if __name__ == "__main__":
    transcript_repo_directory = "../transcripts"
    transcript_git_url = "https://github.com/thechangelog/transcripts"
    Repo.clone_from(transcript_git_url, transcript_repo_directory)

    podcast_name = "podcast"
    root_directory = f"../transcripts/{podcast_name}"

    for file in pathlib.Path(root_directory).iterdir():
        episode_number = int(file.stem.split("-")[-1])
        episode_text = file.read_text()
        parsed, speakers = parse_episode_text(episode_text)
    # print(speakers)
    # break
    # texts.append(episode_text)
