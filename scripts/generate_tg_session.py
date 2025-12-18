from telethon import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("API_ID: "))
api_hash = input("API_HASH: ")

with TelegramClient(StringSession(), api_id, api_hash) as client:
  print("\nPaste this into TELETHON_SESSION:\n")
  print(client.session.save())
