from thechangelogbot.conf.load_config import config
from thechangelogbot.index.database import search_database


def search():
    print(
        search_database(
            config=config,
            query="How are you feeling?",
        )
    )


if __name__ == "__main__":
    search()
