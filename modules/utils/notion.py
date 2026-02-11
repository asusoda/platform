from notion_client import Client

from modules.utils.config import config

notion = Client(auth=config.NOTION_API_KEY)
