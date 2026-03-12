import os

class Config(object):

    BOT_TOKEN = os.environ.get("BOT_TOKEN")

    API_ID = int(os.environ.get("API_ID"))

    API_HASH = os.environ.get("API_HASH")

    DB_NAME = os.environ.get("DB_NAME")

    DB_URL = os.environ.get("DB_URL")

    ADMIN_ID = int(os.environ.get("ADMIN_ID"))

    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL"))

    USERLINK = os.environ.get("USERLINK")

    TUTORIAL_VIDEO = os.environ.get("TUTORIAL_VIDEO")
