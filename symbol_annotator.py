import tkinter as tk
from tkinter import simpledialog, messagebox
from PIL import Image, ImageTk
from classes.symbol import Symbol

class EditSymbolDialog(simpledialog.Dialog):
    """
    A dialog to edit a symbol’s type, X/Y coordinates, amperage, and height.
    Fields for amperage/height appear only for types that support them.
    """
    def __init__(self, parent, symbol, symbol_types, defaults):
        self.symbol = symbol
        self.symbol_types = symbol_types
        self.defaults = defaults
        super().__init__(parent, title="Edit Symbol")

    def body(self, master):
        tk.Label(master, text="Type:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.type_var = tk.StringVar(value=self.symbol.type)
        self.type_menu = tk.OptionMenu(master, self.type_var, *self.symbol_types, command=self.on_type_change)
        self.type_menu.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        tk.Label(master, text="X coordinate:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.x_entry = tk.Entry(master)
        self.x_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.x_entry.insert(0, str(int(self.symbol.coords[0])))

        tk.Label(master, text="Y coordinate:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.y_entry = tk.Entry(master)
        self.y_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.y_entry.insert(0, str(int(self.symbol.coords[1])))

        # Amperage and Height fields (initially hidden if not needed)
        self.amp_label = tk.Label(master, text="Amperage:")
        self.amp_entry = tk.Entry(master)
        self.height_label = tk.Label(master, text="Height:")
        self.height_entry = tk.Entry(master)

        # Pre-fill if existing symbol has these values
        if self.symbol.amperage is not None:
            self.amp_entry.insert(0, str(self.symbol.amperage))
        if self.symbol.height is not None:
            self.height_entry.insert(0, str(self.symbol.height))

        # Show/hide fields based on current type
        self.update_fields()
        return self.type_menu  # initial focus on type dropdown

    def on_type_change(self, selected_type):
        self.update_fields()

    def update_fields(self):
        # Decide which fields to display based on selected type
        current_type = self.type_var.get()
        amperage_default = self.defaults.get(current_type, {}).get("amperage")
        height_default = self.defaults.get(current_type, {}).get("height")

        # Hide all optional fields first
        self.amp_label.grid_forget(); self.amp_entry.grid_forget()
        self.height_label.grid_forget(); self.height_entry.grid_forget()

        row = 3
        if amperage_default is not None:
            self.amp_label.grid(row=row, column=0, padx=5, pady=5, sticky="e")
            self.amp_entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
            row += 1
        if height_default is not None:
            self.height_label.grid(row=row, column=0, padx=5, pady=5, sticky="e")
            self.height_entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")

    def apply(self):
        new_type = self.type_var.get()
        old_type = self.symbol.type

        # Update type if changed, and clear unsupported fields if needed
        if new_type and new_type != old_type:
            self.symbol.type = new_type
            new_defaults = self.defaults.get(new_type, {})
            if new_defaults.get("amperage") is None:
                self.symbol.amperage = None
            if new_defaults.get("height") is None:
                self.symbol.height = None

        # Update X (if provided)
        x_text = self.x_entry.get().strip()
        if x_text:
            try:
                new_x = float(x_text)
                self.symbol.coords = (new_x, self.symbol.coords[1])
            except ValueError:
                messagebox.showerror("Invalid input", "X coordinate must be a number.")
        # Update Y (if provided)
        y_text = self.y_entry.get().strip()
        if y_text:
            try:
                new_y = float(y_text)
                self.symbol.coords = (self.symbol.coords[0], new_y)
            except ValueError:
                messagebox.showerror("Invalid input", "Y coordinate must be a number.")

        # Update amperage if applicable
        amperage_default = self.defaults.get(self.symbol.type, {}).get("amperage")
        if amperage_default is not None:
            amp_text = self.amp_entry.get().strip()
            if amp_text:
                try:
                    self.symbol.amperage = int(amp_text)
                except ValueError:
                    messagebox.showerror("Invalid input", "Amperage must be an integer.")

        # Update height if applicable
        height_default = self.defaults.get(self.symbol.type, {}).get("height")
        if height_default is not None:
            height_text = self.height_entry.get().strip()
            if height_text:
                try:
                    self.symbol.height = int(height_text)
                except ValueError:
                    messagebox.showerror("Invalid input", "Height must be an integer.")


class SymbolAnnotator(tk.Frame):
    """
    A GUI for placing and editing electrical symbols on an image.
    """
    def __init__(self, master, container, on_done):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        self.master = master
        self.container = container
        self.on_done = on_done

        self.symbol_types = self.container['symbol_types']
        self.scale_point_ids = []
        self.defaults = self.container.get('default', {})

        # --- UI Setup ---
        frame = tk.Frame(self)
        frame.pack(fill="x")
        tk.Button(frame, text="Load Image", command=self.load_image).pack(side="left")
        tk.Button(frame, text="Done", command=self.finish).pack(side="left")
        tk.Button(frame, text="Finish Light Selection", command=self.finish_light_selection).pack(side="left")
        self.selected_symbol = tk.StringVar(value=self.symbol_types[0])
        tk.OptionMenu(frame, self.selected_symbol, *self.symbol_types, command=self.symbol_selected).pack(side="left")
        self.status_var = tk.StringVar()
        tk.Label(self, textvariable=self.status_var).pack(fill="x")

        # Canvas and scrollbars
        canvas_frame = tk.Frame(self); canvas_frame.pack(fill="both", expand=True)
        h_scroll = tk.Scrollbar(canvas_frame, orient="horizontal"); h_scroll.pack(side="bottom", fill="x")
        v_scroll = tk.Scrollbar(canvas_frame, orient="vertical"); v_scroll.pack(side="right", fill="y")
        self.canvas = tk.Canvas(canvas_frame, bg="white",
                                xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        h_scroll.config(command=self.canvas.xview); v_scroll.config(command=self.canvas.yview)

        # Annotation list
        summary = tk.Frame(self); summary.pack(fill="x", padx=10, pady=5)
        tk.Label(summary, text="Current Annotations:").pack(anchor="w")
        self.annotation_listbox = tk.Listbox(summary, height=6, width=80)
        self.annotation_listbox.pack(fill="x")

        # Event binding
        self.canvas.bind("<Button-1>", self.click_event)
        self.active_switch = None
        self.img_tk = None
        self.img_id = None
        self.scale_points = []

        self.update_status()
        self.update_annotation_list()

    def load_image(self):
        path = self.container.get("image_path")
        if not path:
            from tkinter import filedialog
            path = filedialog.askopenfilename()
            self.container["image_path"] = path
        if not path: return
        img = Image.open(path)
        self.img_tk = ImageTk.PhotoImage(img)
        if self.img_id:
            self.canvas.delete(self.img_id)
        self.img_id = self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)
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

    def update_status(self):
        current = self.selected_symbol.get()
        self.status_var.set(f"Select all {current}s where they meet the wall.")

    def update_annotation_list(self):
        # Refresh the listbox for currently selected symbol type
        self.annotation_listbox.delete(0, tk.END)
        selected = self.selected_symbol.get()
        for symbol in self.container["symbols"]:
            if symbol.type == selected:
                controls_str = ""
                if symbol.type.lower() == "switch" and symbol.controls:
                    coords = [f"({int(l.coords[0])},{int(l.coords[1])})"
                              for l in symbol.controls]
                    controls_str = " → " + ", ".join(coords)
                info = (f"{symbol.type} (ID:{symbol.id}) at "
                        f"({int(symbol.coords[0])}, {int(symbol.coords[1])}) | "
                        f"Amperage: {symbol.amperage} | Height: {symbol.height} | "
                        f"Room: {symbol.room or 'N/A'}{controls_str}")
                self.annotation_listbox.insert(tk.END, info)

    def click_event(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        # Check if user clicked on an existing symbol
        clicked_symbol = None
        threshold = 6  # pixel radius to detect symbol click
        for symbol in self.container["symbols"]:
            sx, sy = symbol.coords
            if (canvas_x - sx)**2 + (canvas_y - sy)**2 <= threshold**2:
                clicked_symbol = symbol
                break

        if clicked_symbol:
            # Open edit dialog for that symbol
            EditSymbolDialog(self.master, clicked_symbol, self.symbol_types, self.defaults)
            # Redraw after editing
            self.redraw_canvas()
            self.update_annotation_list()
            return

        # Otherwise, add a new symbol at this location
        symbol_type = self.selected_symbol.get()
        default_vals = self.defaults.get(symbol_type, {})
        symbol = Symbol(symbol_type, (canvas_x, canvas_y), room=None,
                        amperage=default_vals.get("amperage"), height=default_vals.get("height"))

        if symbol_type.lower() == "switch":
            self.container["symbols"].append(symbol)
            self.active_switch = symbol
            self.selected_symbol.set("light")
            self.status_var.set("Now click the lights this switch controls.")
            print(f"🟩 Switch placed (ID: {symbol.id}) at {symbol.coords}")

        elif symbol_type.lower() == "light":
            if self.active_switch:
                self.active_switch.controls.append(symbol)
                self.container["symbols"].append(symbol)
                # Draw connection line from switch to light
                sx, sy = self.active_switch.coords
                lx, ly = symbol.coords
                self.canvas.create_line(sx, sy, lx, ly, fill="blue", dash=(2, 2))
                print(f"🔗 Linked switch {self.active_switch.id} → light {symbol.id}")
            else:
                self.status_var.set("⚠️ Place a switch first.")
                return

        else:
            self.container["symbols"].append(symbol)
            self.active_switch = None

        # Draw the new symbol and update list
        self.draw_symbol(symbol)
        self.update_annotation_list()

    def draw_symbol(self, symbol):
        x, y = symbol.coords
        t = symbol.type.lower()
        if t == 'outlet':
            self.canvas.create_oval(x-3, y-3, x+3, y+3, fill="red")
        elif t == 'switch':
            self.canvas.create_oval(x-3, y-3, x+3, y+3, fill="red")
        elif t == 'light':
            self.canvas.create_oval(x-3, y-3, x+3, y+3, fill="yellow")
        elif t == 'junction box':
            self.canvas.create_rectangle(x-8, y-8, x+8, y+8, fill="red")
        elif t == 'electrical panel':
            self.canvas.create_rectangle(x-5, y-15, x+5, y+15, fill="black")

    def redraw_canvas(self):
        # Clear and redraw the image and all symbols/links
        if not self.img_tk: return
        self.canvas.delete("all")
        self.img_id = self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)
        self.canvas.config(scrollregion=(0, 0, self.img_tk.width(), self.img_tk.height()))
        for symbol in self.container["symbols"]:
            self.draw_symbol(symbol)
        # Redraw switch-light lines
        for symbol in self.container["symbols"]:
            if symbol.type.lower() == "switch":
                sx, sy = symbol.coords
                for light in symbol.controls:
                    lx, ly = light.coords
                    self.canvas.create_line(sx, sy, lx, ly, fill="blue", dash=(2, 2))

    def finish_light_selection(self):
        if self.active_switch:
            print(f"✅ Finished assigning lights for switch {self.active_switch.id}")
            self.active_switch = None
            self.status_var.set("Select symbols as usual.")
            self.selected_symbol.set("switch")
        else:
            self.status_var.set("⚠️ No active switch to finish.")

    def finish(self):
        self.pack_forget()
        self.on_done(self.container)
