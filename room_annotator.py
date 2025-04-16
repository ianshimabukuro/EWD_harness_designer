import tkinter as tk
from tkinter import simpledialog
from PIL import Image, ImageTk
from matplotlib.path import Path
from hanan_utils import annotations_to_hanan_grid


class RoomAnnotator(tk.Frame):
    def __init__(self, master,container, on_done):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        self.master = master
        self.on_done = on_done  # for future callback
        self.container = container

        self.canvas_frame = tk.Frame(self)
        self.canvas_frame.pack(fill="both", expand=True)

        self.h_scroll = tk.Scrollbar(self.canvas_frame, orient="horizontal")
        self.h_scroll.pack(side="bottom", fill="x")
        self.v_scroll = tk.Scrollbar(self.canvas_frame, orient="vertical")
        self.v_scroll.pack(side="right", fill="y")

        self.canvas = tk.Canvas(self.canvas_frame, bg="white",
                                xscrollcommand=self.h_scroll.set,
                                yscrollcommand=self.v_scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.config(command=self.canvas.yview)

        
       
       
        self.image = Image.open(self.container['image_path'])
        self.img_tk = ImageTk.PhotoImage(self.image)
        self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)

        self.container['graph'], self.x_coords, self.y_coords, self.container['symbols'] = annotations_to_hanan_grid(self.container['symbols'], scale=1, threshold=10)
        
        self.room_polygons = []
        self.current_polygon = []
        self.dot_room_map = {}

        self.canvas.bind("<Button-1>", self.on_click)

        self.finish_button = tk.Button(self, text="Finish Room", command=self.finish_room)
        self.finish_button.pack()

        self.done_button = tk.Button(self,text = "Done", command = self.done)
        self.done_button.pack()

        self.roomless_count_label = tk.Label(self, text="")
        self.roomless_count_label.pack()

        self.draw_all()
        self.update_roomless_count()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def draw_all(self):
        for x in self.x_coords:
            self.canvas.create_line(x, min(self.y_coords), x, max(self.y_coords), fill="gray", dash=(2, 2))
        for y in self.y_coords:
            self.canvas.create_line(min(self.x_coords), y, max(self.x_coords), y, fill="gray", dash=(2, 2))

        for node in self.container['graph'].nodes():
            x, y = node
            color = "red" if self.container['graph'].nodes[node].get("is_dot") else "blue"

            is_panel = any(s.coords == (x, y) and s.type == "electrical panel" for s in self.container['symbols'])
            if is_panel:
                self.canvas.create_rectangle(x-5, y-5, x+5, y+5, fill="black", tags=f"dot_{x}_{y}")
            else:
                self.canvas.create_oval(x-3, y-3, x+3, y+3, fill=color, tags=f"dot_{x}_{y}")

    def update_roomless_count(self):
        roomless = sum(1 for s in self.container['symbols'] if s.room is None)
        self.roomless_count_label.config(text=f"Symbols without room: {roomless}")

    def on_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        closest = min(self.container['graph'].nodes(), key=lambda n: (n[0]-x)**2 + (n[1]-y)**2)
        self.current_polygon.append(closest)
        self.draw_polygon_preview()

    def draw_polygon_preview(self):
        self.canvas.delete("preview")
        for i in range(1, len(self.current_polygon)):
            x1, y1 = self.current_polygon[i-1]
            x2, y2 = self.current_polygon[i]
            self.canvas.create_line(x1, y1, x2, y2, fill="green", width=2, tags="preview")

    def finish_room(self):
        if len(self.current_polygon) < 3:
            return

        self.canvas.create_line(
            self.current_polygon[-1][0], self.current_polygon[-1][1],
            self.current_polygon[0][0], self.current_polygon[0][1],
            fill="green", width=2
        )

        room_name = simpledialog.askstring("Room Name", "Enter name for this room:", parent=self)
        if not room_name:
            return

        self.room_polygons.append((self.current_polygon[:], room_name))
        self.assign_room_to_dots(self.current_polygon, room_name)

        cx = sum(x for x, y in self.current_polygon) // len(self.current_polygon)
        cy = sum(y for x, y in self.current_polygon) // len(self.current_polygon)
        self.canvas.create_text(cx, cy, text=room_name, fill="black", font=("Arial", 10, "bold"))

        self.current_polygon.clear()
        self.canvas.delete("preview")
        self.update_roomless_count()
    def done(self):
        self.pack_forget() 
        self.on_done(self.container)

    def assign_room_to_dots(self, polygon, room_name):
        poly_path = Path(polygon)
        for node in self.container['graph'].nodes():
            if self.container['graph'].nodes[node].get("is_dot"):
                if poly_path.contains_point(node, radius=1e-6):
                    self.dot_room_map[node] = room_name
                    self.canvas.itemconfig(f"dot_{node[0]}_{node[1]}", fill="green")
                    self.canvas.create_text(node[0]+5, node[1]-5, text=room_name, fill="black", font=("Arial", 8))

        for symbol in self.container['symbols']:
            mapped = (int(symbol.coords[0]), int(symbol.coords[1]))
            if symbol.type != "electrical panel" and mapped in self.dot_room_map and symbol.room is None:
                symbol.room = self.dot_room_map[mapped]

