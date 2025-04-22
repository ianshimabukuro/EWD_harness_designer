import tkinter as tk
from tkinter import filedialog, simpledialog
from PIL import Image, ImageTk
from classes.symbol import Symbol

class SymbolAnnotator(tk.Frame):
    def __init__(self, master,container, on_done):
        super().__init__(master)
        self.pack(fill="both", expand=True)

        #Initialize Passed Argument in the Class
        self.master = master
        self.container = container
        self.on_done = on_done

        #Set up global variables in the container
        self.container['ceiling_height'] = 8
        self.container['default'] = {'outlet': {'amperage': 15, 'height': self.container["ceiling_height"] - 1}, #All in feet and Amps
                                      'switch': {'amperage': 15, 'height': self.container["ceiling_height"] - 4},
                                      'light': {'amperage': 1,'height':self.container["ceiling_height"]},
                                      'junction box': {'amperage': None,'height':self.container["ceiling_height"]},
                                      'electrical panel': {'amperage': None,'height': 6},
                                      }
        self.container["symbols"] = []
        self.container["image_path"] = None

        #Initialize current app variables
        self.symbol_types = ["outlet", "switch","junction box","electrical panel"]
        self.current_symbol_idx = 0
        self.img_tk = None
        self.scale_point_ids = []

        #Initailize current app UI elements
        frame = tk.Frame(self)
        frame.pack(fill="x")

        tk.Button(frame, text="Load Image", command=self.load_image).pack(side="left")
        tk.Button(frame, text="Done", command=self.finish).pack(side="left")
        self.selected_symbol = tk.StringVar(value=self.symbol_types[0])
        tk.OptionMenu(frame, self.selected_symbol, *self.symbol_types, command=self.symbol_selected).pack(side="left")

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


        # Summary display frame
        summary_frame = tk.Frame(self)
        summary_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(summary_frame, text="Current Annotations:").pack(anchor="w")

        self.annotation_listbox = tk.Listbox(summary_frame, height=6, width=80)
        self.annotation_listbox.pack(fill="x")

        self.canvas.bind("<Button-1>", self.click_event)
        self.scale_points = []

        self.update_status()

    def load_image(self):
        self.container["image_path"] = filedialog.askopenfilename()
        if not self.container["image_path"]:
            return
        img = Image.open(self.container["image_path"])
        self.img_tk = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)
        self.canvas.config(scrollregion=(0, 0, self.img_tk.width(), self.img_tk.height()))
        self.begin_scale_collection()

    def begin_scale_collection(self):
        self.scale_points.clear()
        self.scale_set = False
        self.status_var.set("Right-click two points with known real-world distance to set the scale.")
        self.canvas.unbind("<Button-1>")
        self.canvas.bind("<Button-1>", self.collect_scale_point)

    def collect_scale_point(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        self.scale_points.append((canvas_x, canvas_y))
        dot_id = self.canvas.create_oval(canvas_x - 3, canvas_y - 3, canvas_x + 3, canvas_y + 3, outline="blue", width=2)
        self.scale_point_ids.append(dot_id)
        if len(self.scale_points) == 2:
            self.canvas.unbind("<Button-1>")  # Done collecting
            self.canvas.bind("<Button-1>", self.click_event)
            self.prompt_for_scale()

    def prompt_for_scale(self):
        x1, y1 = self.scale_points[0]
        x2, y2 = self.scale_points[1]
        pixel_distance = ((x2 - x1)**2 + (y2 - y1)**2)**0.5

        real_distance = simpledialog.askfloat("Set Scale", "Enter the real-world distance between the two points (in feet):", parent=self.master)

        if real_distance and pixel_distance > 0:
            scale = real_distance / pixel_distance
            self.container['scale'] = scale
            self.scale_set = True
            self.status_var.set(f"📐 Scale set: {scale:.4f} ft per pixel")
            print(f"Scale set: {scale:.4f} ft/pixel")
        else:
            self.status_var.set("⚠️ Invalid distance or too short. Please reload image to retry.")
            print("⚠️ Invalid scale input.")
        for dot_id in self.scale_point_ids:
            self.canvas.delete(dot_id)
        self.scale_point_ids.clear()
        self.scale_points.clear()


    def symbol_selected(self, value):
        self.update_status()
        self.update_annotation_list()

    def update_annotation_list(self):
        selected_type = self.selected_symbol.get()
        self.annotation_listbox.delete(0, tk.END)  # Clear previous entries

        for symbol in self.container["symbols"]:
            if symbol.type == selected_type:
                if symbol.type == "switch":
                    controlled_ids = [f"({int(l.coords[0])},{int(l.coords[1])})" for l in symbol.controls]
                    controls_str = " → " + ", ".join(controlled_ids)
                else:
                    controls_str = ""
                info = f"{symbol.type} (ID:{symbol.id}) at ({int(symbol.coords[0])}, {int(symbol.coords[1])}) | Amperage: {symbol.amperage} | Height: {symbol.height} | Room: {symbol.room or 'N/A'}{controls_str}"
                self.annotation_listbox.insert(tk.END, info)

    def click_event(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
    
        symbol_type = self.selected_symbol.get()
        default = self.container['default'][symbol_type]
        symbol = Symbol(symbol_type, (canvas_x, canvas_y), room=None, amperage=default["amperage"], height=default["height"])
        self.container["symbols"].append(symbol)

        if symbol_type == "switch":
            self.status_var.set("Click on lights this switch controls. Right-click when done.")
            self.canvas.unbind("<Button-1>")
            self.canvas.bind("<Button-1>", lambda e, s=symbol: self.select_controlled_lights(e, s))
            self.canvas.bind("<Button-3>", self.end_light_selection)
        else:
            self.update_annotation_list()

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
        self.update_annotation_list()
    def select_controlled_lights(self, event, switch_symbol):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        # Find nearest light within a certain radius
        for symbol in self.container["symbols"]:
            if symbol.type == "light":
                sx, sy = symbol.coords
                dist = ((canvas_x - sx)**2 + (canvas_y - sy)**2)**0.5
                if dist < 15:  # pixel radius threshold
                    if symbol not in switch_symbol.controls:
                        switch_symbol.controls.append(symbol)
                        self.canvas.create_line(switch_symbol.coords[0], switch_symbol.coords[1], sx, sy, fill="blue", dash=(2, 2))
                        print(f"Linked switch {switch_symbol.id} → light at ({int(sx)}, {int(sy)})")
                    break
    def end_light_selection(self, event):
        self.canvas.unbind("<Button-1>")
        self.canvas.unbind("<Button-3>")
        self.canvas.bind("<Button-1>", self.click_event)
        self.status_var.set("Select symbols as usual.")
        self.update_annotation_list()

    def update_status(self):
        current = self.selected_symbol.get()
        self.status_var.set(f"Select all {current}s where they meet the wall.")

    def finish(self):
        print(self.container)
        self.pack_forget() 
        self.on_done(self.container)