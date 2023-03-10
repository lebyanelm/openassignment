import random_utilities.models.time_created


class User():
    def __init__(self, data) -> None:
        # The time this user joined the platform.
        self.time_created = data.get("time_created",
                                    random_utilities.models.time_created.TimeCreatedModel().__dict__)
        
        # Basic identification details retrieved from a Twilio Incoming Message.
        self.whatsapp_id = data.get("whatsapp_id")
        self.profile_name = data.get("profile_name")
        self.from_ = data.get("from_")

        # Groups of messages made in a single day for better context.
        # Conversations should expire the next day. When a conversation expires,
        # Let users know the conversion has expired, but they are allowed to restart it
        self.conversations = data.get("conversations", [])

        # User will be allowed to top-up their account for the user of the bot.
        self.available_funds = data.get("available_amount", 5)
        self.email_address = data.get("email_address", None)
        self.version = (1, 0, 0)
