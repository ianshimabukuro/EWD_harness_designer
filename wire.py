import uuid

class Wire:
    def __init__(self,path,start_symbol,end_symbol,scale):
        """
        Class parameters:
        id, path, start_symbol, end_symbol, scale, type, length, gauge
        """
        self.id = uuid.uuid4().hex[:6]
        self.path = path
        self.start_symbol = start_symbol
        self.end_symbol =  end_symbol
        self.scale = scale

        #Internal Logic to Categorize Wire and Extract Information
        if start_symbol.type != 'Junction Box':
            self.type = 'Room Wire'
        else:
            self.type = 'Home Run Wire'
        self.get_length_ft()
        self.gauge = self.get_gauge()
        
    
    def get_length_ft(self):
        total_length = sum(
                    ((self.path[i+1][0]-self.path[i][0])**2 + (self.path[i+1][1]-self.path[i][1])**2)**0.5
                    for i in range(len(self.path)-1)
                )*self.scale
        if self.type == 'Room Wire':
            total_length += self.start_symbol.height
        else:
            total_length += self.end_symbol.height
        self.length = total_length

    def get_gauge(self):
        if self.start_symbol.amperage <= 15:
            return "14 AWG" if self.length <= 50 else "12 AWG"
        elif self.start_symbol.amperage <= 20:
            return "12 AWG" if self.length <= 50 else "10 AWG"
        elif self.start_symbol.amperage <= 30:
            return "10 AWG" if self.length <= 50 else "8 AWG"
        else:
            return "Consult engineer"

    def __str__(self):
        print(f"path")