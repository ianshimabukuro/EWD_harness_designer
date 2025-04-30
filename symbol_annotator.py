import tkinter as tk
from tkinter import filedialog, simpledialog
from PIL import Image, ImageTk
from classes.symbol import Symbol

class EditSymbolDialog(simpledialog.Dialog):
    def __init__(self, parent, symbol):
        self.parent = parent
        self.symbol = symbol
        super().__init__(parent, title="Edit Symbol")

    def body(self, master):
        # Symbol Type (non-editable)
        tk.Label(master, text="Type:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text=self.symbol.type).grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # X coordinate
        tk.Label(master, text="X:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.x_var = tk.DoubleVar(value=self.symbol.coords[0])
        tk.Entry(master, textvariable=self.x_var).grid(row=1, column=1, padx=5, pady=5)

        # Y coordinate
        tk.Label(master, text="Y:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.y_var = tk.DoubleVar(value=self.symbol.coords[1])
        tk.Entry(master, textvariable=self.y_var).grid(row=2, column=1, padx=5, pady=5)

        # Amperage
        tk.Label(master, text="Amperage:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.amperage_var = tk.StringVar(value=self.symbol.amperage)
        tk.Entry(master, textvariable=self.amperage_var).grid(row=3, column=1, padx=5, pady=5)

        # Height
        tk.Label(master, text="Height:").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.height_var = tk.StringVar(value=self.symbol.height)
        tk.Entry(master, textvariable=self.height_var).grid(row=4, column=1, padx=5, pady=5)

        # Room
        tk.Label(master, text="Room:").grid(row=5, column=0, sticky="e", padx=5, pady=5)
        room_val = self.symbol.room if self.symbol.room is not None else ""
        self.room_var = tk.StringVar(value=room_val)
        tk.Entry(master, textvariable=self.room_var).grid(row=5, column=1, padx=5, pady=5)

    def buttonbox(self):
        box = tk.Frame(self)
        box.pack(padx=5, pady=5)

        save_btn = tk.Button(box, text="Save", width=10, command=self.ok)
        save_btn.pack(side="left", padx=5)
        delete_btn = tk.Button(box, text="Delete", width=10, command=self.on_delete)
        delete_btn.pack(side="left", padx=5)
        cancel_btn = tk.Button(box, text="Cancel", width=10, command=self.cancel)
        cancel_btn.pack(side="left", padx=5)

    def apply(self):
        # Update symbol attributes from dialog inputs
        try:
            x = float(self.x_var.get())
            y = float(self.y_var.get())
        except ValueError:
            x, y = self.symbol.coords
        self.symbol.coords = (x, y)
        self.symbol.amperage = self.amperage_var.get()
        self.symbol.height = self.height_var.get()
        room_val = self.room_var.get().strip()
        self.symbol.room = room_val if room_val else None
        # Refresh parent UI
        self.parent.update_annotation_list()
        self.parent.redraw_symbols()

    def on_delete(self):
        # Delete symbol from parent and refresh UI
        self.parent.delete_symbol(self.symbol)
        self.parent.update_annotation_list()
        self.parent.redraw_symbols()
        self.destroy()

class SymbolAnnotator(tk.Frame):
    def __init__(self, master, container, on_done):
        super().__init__(master)
        self.master = master
        self.container = container
        self.on_done = on_done

        self.symbol_types = self.container['symbol_types']
        self.scale_point_ids = []
        self.active_switch = None

        # Top controls: Load, Done, Finish Light, Symbol type selection
        control_frame = tk.Frame(self)
        control_frame.pack(fill="x", pady=5)
        tk.Button(control_frame, text="Load Image", command=self.load_image).pack(side="left", padx=5)
        tk.Button(control_frame, text="Done", command=self.finish).pack(side="left", padx=5)
        tk.Button(control_frame, text="Finish Light Selection", command=self.finish_light_selection).pack(side="left", padx=5)
        self.selected_symbol = tk.StringVar(value=self.symbol_types[0])
        tk.OptionMenu(control_frame, self.selected_symbol, *self.symbol_types, command=self.symbol_selected).pack(side="left", padx=5)

        self.status_var = tk.StringVar()
        tk.Label(self, textvariable=self.status_var).pack(fill="x")

        # Canvas and scrollbars
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

        # Annotation list display
        summary_frame = tk.Frame(self)
        summary_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(summary_frame, text="Current Annotations:").pack(anchor="w")
        self.annotation_listbox = tk.Listbox(summary_frame, height=6, width=80)
        self.annotation_listbox.pack(fill="x")
        self.annotation_listbox.bind("<Double-Button-1>", self.edit_symbol)

        # Initialize scale state
        self.scale_points = []
        self.update_status()
        self.canvas.bind("<Button-1>", self.click_event)

    def load_image(self):
        self.container["image_path"] = filedialog.askopenfilename()
        if not self.container.get("image_path"):
            return
        img = Image.open(self.container["image_path"])
        self.img = img
        self.img_tk = ImageTk.PhotoImage(img)
        # Draw the image on canvas with a tag
        self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk, tags="floorplan")
        self.canvas.config(scrollregion=(0, 0, self.img_tk.width(), self.img_tk.height()))
        self.begin_scale_collection()

    def begin_scale_collection(self):
        self.scale_points.clear()
        self.status_var.set("Right-click two points with known real-world distance to set the scale.")
        self.canvas.unbind("<Button-1>")
        self.canvas.bind("<Button-3>", self.collect_scale_point)

    def collect_scale_point(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        self.scale_points.append((canvas_x, canvas_y))
        dot_id = self.canvas.create_oval(canvas_x - 3, canvas_y - 3, canvas_x + 3, canvas_y + 3,
                                         outline="blue", width=2)
        self.scale_point_ids.append(dot_id)
        if len(self.scale_points) == 2:
            self.canvas.unbind("<Button-3>")  # Done collecting scale points
            self.canvas.bind("<Button-1>", self.click_event)
            self.prompt_for_scale()

    def prompt_for_scale(self):
        (x1, y1), (x2, y2) = self.scale_points
        pixel_distance = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
        real_distance = simpledialog.askfloat(
            "Set Scale", "Enter the real-world distance between the two points (in feet):", parent=self.master)
        if real_distance and pixel_distance > 0:
            scale = real_distance / pixel_distance
            self.container['scale'] = scale
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
        self.annotation_listbox.delete(0, tk.END)
        for symbol in list(self.container["symbols"]):
            if symbol.type == selected_type:
                if symbol.type == "switch":
                    controlled_ids = [f"({int(l.coords[0])},{int(l.coords[1])})" for l in symbol.controls]
                    controls_str = " → " + ", ".join(controlled_ids) if controlled_ids else ""
                else:
                    controls_str = ""
                info = (f"{symbol.type} (ID:{symbol.id}) at ({int(symbol.coords[0])}, "
                        f"{int(symbol.coords[1])}) | Amperage: {symbol.amperage} | Height: "
                        f"{symbol.height} | Room: {symbol.room or 'N/A'}{controls_str}")
                self.annotation_listbox.insert(tk.END, info)

    def click_event(self, event):
        if self.active_switch and self.selected_symbol.get() != "light":
            self.status_var.set("⚠️ Finish placing lights before selecting another symbol.")
            return
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        symbol_type = self.selected_symbol.get()
        default = self.container['default'][symbol_type]
        symbol = Symbol(symbol_type, (canvas_x, canvas_y), room=None,
                        amperage=default["amperage"], height=default["height"])
        if symbol_type == "switch":
            self.container["symbols"].append(symbol)
            self.active_switch = symbol
            self.selected_symbol.set("light")
            self.status_var.set("Now click the lights this switch controls.")
            print(f"🟩 Switch placed (ID: {symbol.id}) at {symbol.coords}")
        elif symbol_type == "light":
            if self.active_switch:
                self.active_switch.controls.append(symbol)
                self.container["symbols"].append(symbol)
                self.canvas.create_line(self.active_switch.coords[0], self.active_switch.coords[1],
                                        symbol.coords[0], symbol.coords[1],
                                        fill="blue", dash=(2, 2), tags="link")
                print(f"🔗 Linked switch {self.active_switch.id} → light {symbol.id}")
            else:
                self.status_var.set("⚠️ Place a switch first.")
                return
        else:
            self.container["symbols"].append(symbol)
            self.active_switch = None
        # Draw the symbol on canvas
        x, y = symbol.coords
        x1, y1, x2, y2 = x-3, y-3, x+3, y+3
        if symbol_type == 'outlet':
            self.canvas.create_oval(x1, y1, x2, y2, fill="red", tags="symbol")
        elif symbol_type == 'switch':
            self.canvas.create_oval(x1, y1, x2, y2, fill="red", tags="symbol")
        elif symbol_type == 'light':
            self.canvas.create_oval(x1, y1, x2, y2, fill="yellow", tags="symbol")
        elif symbol_type == 'junction box':
            self.canvas.create_rectangle(x-8, y-8, x+8, y+8, fill="red", tags="symbol")
        elif symbol_type == 'electrical panel':
            self.canvas.create_rectangle(x-5, y-15, x+5, y+15, fill="black", tags="symbol")
        self.update_annotation_list()

    def edit_symbol(self, event):
        selection = self.annotation_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        selected_type = self.selected_symbol.get()
        count = 0
        target_symbol = None
        for symbol in self.container["symbols"]:
            if symbol.type == selected_type:
                if count == index:
                    target_symbol = symbol
                    break
                count += 1
        if target_symbol:
            EditSymbolDialog(self, target_symbol)

    def delete_symbol(self, symbol):
        # Remove symbol and related lights
        if symbol in self.container["symbols"]:
            if symbol.type == "switch":
                # Remove lights controlled by this switch
                for light in list(symbol.controls):
                    if light in self.container["symbols"]:
                        self.container["symbols"].remove(light)
                self.container["symbols"].remove(symbol)
            elif symbol.type == "light":
                # Remove light from any switch controls
                for sym in self.container["symbols"]:
                    if sym.type == "switch" and symbol in sym.controls:
                        sym.controls.remove(symbol)
                self.container["symbols"].remove(symbol)
            else:
                self.container["symbols"].remove(symbol)

    def redraw_symbols(self):
        # Clear existing symbols and links (keep the background image)
        self.canvas.delete("symbol")
        self.canvas.delete("link")
        # Redraw link lines
        for symbol in self.container["symbols"]:
            if symbol.type == "switch":
                for light in symbol.controls:
                    self.canvas.create_line(symbol.coords[0], symbol.coords[1],
                                            light.coords[0], light.coords[1],
                                            fill="blue", dash=(2, 2), tags="link")
        # Redraw symbols
        for symbol in self.container["symbols"]:
            x, y = symbol.coords
            x1, y1, x2, y2 = x-3, y-3, x+3, y+3
            if symbol.type == 'outlet':
                self.canvas.create_oval(x1, y1, x2, y2, fill="red", tags="symbol")
            elif symbol.type == 'switch':
                self.canvas.create_oval(x1, y1, x2, y2, fill="red", tags="symbol")
            elif symbol.type == 'light':
                self.canvas.create_oval(x1, y1, x2, y2, fill="yellow", tags="symbol")
            elif symbol.type == 'junction box':
                self.canvas.create_rectangle(x-8, y-8, x+8, y+8, fill="red", tags="symbol")
            elif symbol.type == 'electrical panel':
                self.canvas.create_rectangle(x-5, y-15, x+5, y+15, fill="black", tags="symbol")

    def finish_light_selection(self):
        if self.active_switch:
            print(f"✅ Finished assigning lights for switch {self.active_switch.id}")
            self.active_switch = None
            self.status_var.set("Select symbols as usual.")
            self.selected_symbol.set("switch")
        else:
            self.status_var.set("⚠️ No active switch to finish.")

    def update_status(self):
        current = self.selected_symbol.get()
        self.status_var.set(f"Select all {current}s where they meet the wall.")

    def finish(self):
        print(self.container)
        self.pack_forget()
        self.on_done(self.container)
