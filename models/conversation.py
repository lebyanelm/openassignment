import random_utilities.models.time_created


class Conversation():
    def __init__(self, data = dict()) -> None:
        self.time_created = data.get("time_created",
                                    random_utilities.models.time_created.TimeCreatedModel().__dict__)

        self.messages = data.get("messages", list())
        self.version = (1, 0, 0)
