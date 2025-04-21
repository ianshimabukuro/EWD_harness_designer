import uuid
class Symbol:
    def __init__(self,type,coords,room,amperage,height):
        self.id = uuid.uuid4().hex[:6]
        self.type = type
        self.coords = coords
        self.room = room
        self.amperage = amperage
        self.height = height
        self.controls = []

    def __str__(self):
        print(f"{self.id},{self.type},{self.coords},{self.room},{self.amperage},{self.height}")