import tkinter as tk
from tkinter import filedialog, simpledialog
from PIL import Image, ImageTk
from classes.symbol import Symbol

class SymbolAnnotator(tk.Frame):
    def __init__(self, master,container, on_done):
        super().__init__(master)
        self.pack(fill="both", expand=True)

        
        self.master = master
        self.container = container
        self.on_done = on_done

        #Initialize current app variables
        self.symbol_types = self.container['symbol_types']
        self.scale_point_ids = []
        self.active_switch = None

        #Initailize current app UI elements
        frame = tk.Frame(self)
        frame.pack(fill="x")
        tk.Button(frame, text="Load Image", command=self.load_image).pack(side="left")
        tk.Button(frame, text="Done", command=self.finish).pack(side="left")
        tk.Button(frame, text="Finish Light Selection", command=self.finish_light_selection).pack(side="left")
        
        self.selected_symbol = tk.StringVar(value=self.symbol_types[0])
        tk.OptionMenu(frame, self.selected_symbol, *self.symbol_types, command=self.symbol_selected).pack(side="left")
       
        self.status_var = tk.StringVar()
        tk.Label(self, textvariable=self.status_var).pack(fill="x")

        #Scroll bars
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


        # Annotation Display UI
        summary_frame = tk.Frame(self)
        summary_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(summary_frame, text="Current Annotations:").pack(anchor="w")
        self.annotation_listbox = tk.Listbox(summary_frame, height=6, width=80)
        self.annotation_listbox.pack(fill="x")

        #Bindings and Others
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
        if self.active_switch and self.selected_symbol.get() != "light":
            self.status_var.set("⚠️ Finish placing lights before selecting another symbol.")
            return  # Block any symbol that isn't a light until light selection is done

        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        symbol_type = self.selected_symbol.get()
        default = self.container['default'][symbol_type]
        symbol = Symbol(symbol_type, (canvas_x, canvas_y), room=None, amperage=default["amperage"], height=default["height"])

        if symbol_type == "switch":
            self.container["symbols"].append(symbol)
            self.active_switch = symbol
            self.selected_symbol.set("light")  # Force light selection mode
            self.status_var.set("Now click the lights this switch controls.")
            print(f"🟩 Switch placed (ID: {symbol.id}) at {symbol.coords}")

        elif symbol_type == "light":
            if self.active_switch:
                self.active_switch.controls.append(symbol)
                self.container["symbols"].append(symbol)
                self.canvas.create_line(
                    self.active_switch.coords[0], self.active_switch.coords[1],
                    symbol.coords[0], symbol.coords[1],
                    fill="blue", dash=(2, 2)
                )
                print(f"🔗 Linked switch {self.active_switch.id} → light {symbol.id}")
            else:
                self.status_var.set("⚠️ Place a switch first.")
                return

        else:
            self.container["symbols"].append(symbol)
            self.active_switch = None

        # Draw the symbol
        match symbol_type:
            case 'outlet':
                self.canvas.create_oval(canvas_x-3, canvas_y-3, canvas_x+3, canvas_y+3, fill="red")
            case 'switch':
                self.canvas.create_oval(canvas_x-3, canvas_y-3, canvas_x+3, canvas_y+3, fill="red")
            case 'light':
                self.canvas.create_oval(canvas_x-3, canvas_y-3, canvas_x+3, canvas_y+3, fill="yellow")
            case 'junction box':
                self.canvas.create_rectangle(canvas_x-8, canvas_y-8, canvas_x+8, canvas_y+8, fill="red")
            case 'electrical panel':
                self.canvas.create_rectangle(canvas_x-5, canvas_y-15, canvas_x+5, canvas_y+15, fill="black")

        self.update_annotation_list()

    def finish_light_selection(self):
        if self.active_switch:
            print(f"✅ Finished assigning lights for switch {self.active_switch.id}")
            self.active_switch = None
            self.status_var.set("Select symbols as usual.")
            self.selected_symbol.set("switch")  # Optional: reset dropdown back to switch
        else:
            self.status_var.set("⚠️ No active switch to finish.")

    def update_status(self):
        current = self.selected_symbol.get()
        self.status_var.set(f"Select all {current}s where they meet the wall.")

    def finish(self):
        print(self.container)
        self.pack_forget() 
        self.on_done(self.container)