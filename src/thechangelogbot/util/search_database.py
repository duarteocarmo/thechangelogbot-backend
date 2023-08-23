from thechangelogbot.conf.load_config import config
from thechangelogbot.index.database import search_database

if __name__ == "__main__":
    search_database(
        config=config,
        query="How are you feeling?",
        list_of_filters={
            "podcast": "brainscience",
            "speaker": "Danielle",
        },
    )
