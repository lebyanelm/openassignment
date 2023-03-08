class Message():
    def __init__(self, data) -> None:        
        self.content = data.get("content")
        self.role = data.get("role")