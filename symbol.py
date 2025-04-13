class Symbol:
    def __init__(self,id,type,coords,room,amperage,height):
        self.id = id
        self.type = type
        self.coords = coords
        self.room = room
        self.amperage = int(amperage)
        self.height = height

    def __str__(self):
        print(f"{self.id},{self.type},{self.coords},{self.room},{self.amperage},{self.height}")