import tkinter as tk
from tkinter import filedialog, simpledialog
from PIL import Image, ImageTk
from symbol import Symbol
import uuid

class SymbolAnnotator(tk.Frame):
    def __init__(self, master, on_done):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        self.master = master
        self.on_done = on_done

        # Ask for default amperage and height for each symbol type
        self.symbol_types = ["outlet", "switch","junction box","electrical panel"]
        self.symbol_defaults = {}
        for symbol in self.symbol_types:
            amperage = simpledialog.askstring("Input", f"Enter default amperage for {symbol}s:", parent=master)
            height = simpledialog.askstring("Input", f"Enter default height for {symbol}s:", parent=master)
            self.symbol_defaults[symbol] = {"amperage": amperage, "height": height}

        self.current_symbol_idx = 0
        self.annotations = []
        self.image_path = None
        self.img_tk = None

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
        self.image_path = filedialog.askopenfilename()
        if not self.image_path:
            return
        img = Image.open(self.image_path)
        self.img_tk = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)
        self.canvas.config(scrollregion=(0, 0, self.img_tk.width(), self.img_tk.height()))

    def click_event(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        symbol_id = uuid.uuid1()
        symbol_type = self.symbol_types[self.current_symbol_idx]
        default = self.symbol_defaults[symbol_type]
        symbol = Symbol(symbol_id,symbol_type, (canvas_x, canvas_y), room=None, amperage=default["amperage"], height=default["height"])
        self.annotations.append(symbol)
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
        self.pack_forget() 
        self.on_done(self.annotations, self.image_path)