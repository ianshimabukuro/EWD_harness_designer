import tkinter as tk
from tkinter import filedialog, simpledialog
from PIL import Image, ImageTk
from symbol import Symbol
import uuid

class SymbolAnnotator(tk.Frame):
    def __init__(self, master,container, on_done):
        super().__init__(master)
        self.pack(fill="both", expand=True)

        #Initialize Passed Argument in the Class
        self.master = master
        self.container = container
        self.on_done = on_done

        

        #Set up global variables in the container
        self.container['ceiling_height'] = 96
        self.container['default'] = {'outlet': {'amperage': 15, 'height': 16}, #All in inches
                                      'switch': {'amperage': 15, 'height': 48},
                                      'light': {'amperage': 1,'height':self.container["ceiling_height"]},
                                      'junction box': {'amperage': None,'height':self.container["ceiling_height"]},
                                      'electrical panel': {'amperage': None,'height': 70},
                                      }
        self.container["symbols"] = []
        self.container["image_path"] = None

        #Initialize current app variables
        self.symbol_types = ["outlet", "switch","light","junction box","electrical panel"]
        self.current_symbol_idx = 0
        self.img_tk = None

        #Initailize current app UI elements
        frame = tk.Frame(self)
        frame.pack(fill="x")

        tk.Button(frame, text="Load Image", command=self.load_image).pack(side="left")
        tk.Button(frame, text="Next", command=self.next_symbol).pack(side="left")

        self.status_var = tk.StringVar()
        tk.Label(self, textvariable=self.status_var).pack(fill="x")

        canvas_frame = tk.Frame(self)
        canvas_frame.pack(fill="both", expand=True)

        h_scroll = tk.Scrollbar(canvas_frame, orient="horizontal")
        h_scroll.pack(side="bottom", fill="x")
        v_scroll = tk.Scrollbar(canvas_frame, orient="vertical")
        v_scroll.pack(side="right", fill="y")

        self.canvas = tk.Canvas(canvas_frame, bg="white", xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)

        h_scroll.config(command=self.canvas.xview)
        v_scroll.config(command=self.canvas.yview)
        self.canvas.bind("<Button-1>", self.click_event)

        self.update_status()

    def load_image(self):
        self.container["image_path"] = filedialog.askopenfilename()
        if not self.container["image_path"]:
            return
        img = Image.open(self.container["image_path"])
        self.img_tk = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)
        self.canvas.config(scrollregion=(0, 0, self.img_tk.width(), self.img_tk.height()))
        scale = simpledialog.askfloat('Input',f'Input the DPI scale of the current image', parent = self.master)
        self.container['scale'] = scale
        

    def click_event(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        symbol_id = uuid.uuid1()
        symbol_type = self.symbol_types[self.current_symbol_idx]
        default = self.container['default'][symbol_type]
        symbol = Symbol(symbol_id,symbol_type, (canvas_x, canvas_y), room=None, amperage=default["amperage"], height=default["height"])
        self.container["symbols"].append(symbol)
        match symbol_type:
            case 'outlet':
                self.canvas.create_oval(canvas_x-3, canvas_y-3, canvas_x+3, canvas_y+3, fill="red")
            case 'switch':
                self.canvas.create_oval(canvas_x-3, canvas_y-3, canvas_x+3, canvas_y+3, fill="red")
            case 'junction box':
                self.canvas.create_rectangle(canvas_x-8, canvas_y-8, canvas_x+8, canvas_y+8, fill="red")
            case 'electrical panel':
                self.canvas.create_rectangle(canvas_x-5, canvas_y-15, canvas_x+5, canvas_y+15, fill="black")
            case _:
                self.canvas.create_oval(canvas_x-3, canvas_y-3, canvas_x+3, canvas_y+3, fill="red")


    def next_symbol(self):
        if self.current_symbol_idx + 1 < len(self.symbol_types):
            self.current_symbol_idx += 1
            self.update_status()
        else:
            self.finish()

    def update_status(self):
        current = self.symbol_types[self.current_symbol_idx]
        self.status_var.set(f"Select all {current}s where they meet the wall, then click 'Next'")

    def finish(self):
        print(self.container)
        self.pack_forget() 
        self.on_done(self.container)