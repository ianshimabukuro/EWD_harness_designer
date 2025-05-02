import uuid
class Symbol:
    def __init__(self,type,coords,room,amperage,height,id=None):
        self.id = id or uuid.uuid4().hex[:6]
        self.type = type
        self.coords = coords
        self.room = room
        self.amperage = amperage
        self.height = height
        self.controls = []

    def __str__(self):
        print(f"{self.id},{self.type},{self.coords},{self.room},{self.amperage},{self.height}")
    
    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "coords": list(self.coords),
            "room": self.room,
            "amperage": self.amperage,
            "height": self.height,
            "controls": [l.id for l in self.controls] if self.type == "switch" else []
        }
    
    @staticmethod
    def from_dict(data, all_symbols=None):
        s = Symbol(
            type=data["type"],
            coords=tuple(data["coords"]),
            room=data.get("room"),
            amperage=data.get("amperage"),
            height=data.get("height"),
            id=data["id"]
        )
        if s.type == "switch" and all_symbols:
            # Post-link controlled lights after all symbols loaded
            s.controls = [sym for sym in all_symbols if sym.id in data.get("controls", [])]
        return s