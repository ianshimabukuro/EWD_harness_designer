import tkinter as tk
from tkinter import filedialog, simpledialog
from PIL import Image, ImageTk
import json
import itertools
import networkx as nx
from matplotlib.path import Path
import matplotlib.pyplot as plt
from collections import defaultdict


def cluster_axis(values, threshold):
    """
    separates list of coordinate values into their own clusters based on proximity

    Args:
        values([int]): list of coordinates (x or y)
        threshold(float): minimun threshold distance between two points

    Returns:
        clusters([[int]]): list of list coordinates per cluster
    """
    values = sorted(values)
    clusters = []
    current_cluster = [values[0]]
    for v in values[1:]:
        if abs(v - current_cluster[-1]) < threshold:
            current_cluster.append(v)
        else:
            clusters.append(current_cluster)
            current_cluster = [v]
    clusters.append(current_cluster)
    return clusters

def create_axis_mapping(clusters):
    """
    averages the cluster and assigns all of them the mean value

    Args:
        clusters([int]): list of list coordinates per cluster
    Returns:
        mapping({int:int}): {previous coordinates: new averaged value}
    """
    mapping = {}
    for cluster in clusters:
        canonical = sum(cluster) // len(cluster)
        for v in cluster:
            mapping[v] = canonical
    return mapping

def annotations_to_hanan_grid(symbols, scale=1, threshold=10):
    """
    Converts a list of Symbol objects into a Hanan grid graph, clustering coordinates,
    and updates each symbol's coords to the snapped grid-aligned position.

    Args:
        symbols (List[Symbol]): List of Symbol objects with raw .coords
        scale (float): optional coordinate scale factor
        threshold (float): clustering threshold for aligning close points

    Returns:
        G (NetworkX Graph): Hanan grid made from snapped coordinates
        x_coords ([int]): Unique snapped x coordinates
        y_coords ([int]): Unique snapped y coordinates
        symbols (List[Symbol]): The same list, with updated .coords
    """
    # Step 1: Collect original coordinates
    raw_coords = [(int(s.coords[0] * scale), int(s.coords[1] * scale)) for s in symbols]

    # Step 2: Cluster axes
    raw_x = sorted(set(x for x, _ in raw_coords))
    raw_y = sorted(set(y for _, y in raw_coords))
    x_map = create_axis_mapping(cluster_axis(raw_x, threshold))
    y_map = create_axis_mapping(cluster_axis(raw_y, threshold))

    # Step 3: Update symbol coordinates in-place
    for s in symbols:
        x_raw, y_raw = int(s.coords[0] * scale), int(s.coords[1] * scale)
        s.coords = (x_map[x_raw], y_map[y_raw])

    # Step 4: Extract snapped coordinates for graph
    snapped_coords = [s.coords for s in symbols]
    x_coords = sorted(set(x_map[x] for x in raw_x))
    y_coords = sorted(set(y_map[y] for y in raw_y))

    # Step 5: Build Hanan grid graph
    G = nx.grid_2d_graph(len(x_coords), len(y_coords))
    index_to_coord = {(i, j): (x, y) for i, x in enumerate(x_coords) for j, y in enumerate(y_coords)}
    G = nx.relabel_nodes(G, index_to_coord)

    # Step 6: Mark points that were originally annotated
    for node in G.nodes():
        G.nodes[node]['is_dot'] = node in snapped_coords

    return G, x_coords, y_coords, symbols

def draw_paths_on_grid(graph, paths_by_room):
    pos = {node: node for node in graph.nodes()}

    plt.figure(figsize=(10, 10))
    nx.draw(graph, pos=pos, node_size=10, node_color="lightgray", edge_color="lightgray")

    colors = ["red", "green", "blue", "orange", "purple", "cyan"]
    for i, (room, paths) in enumerate(paths_by_room.items()):
        for path in paths:
            edges = list(zip(path, path[1:]))
            nx.draw_networkx_edges(graph, pos, edgelist=edges, width=2, edge_color=colors[i % len(colors)])
    
    plt.title("Shortest Paths from Devices to Junction Boxes")
    plt.axis("equal")
    plt.show()

class Symbol:
    def __init__(self,name,coords,room,amperage,height):
        self.name = name
        self.coords = coords
        self.room = room
        self.amperage = amperage
        self.height = height

    def __str__(self):
        print(f"{self.name},{self.coords},{self.room},{self.amperage},{self.height}")

# === Symbol Annotator ===

class SymbolAnnotator:
    def __init__(self, master, on_done_callback):
        self.master = master
        self.on_done_callback = on_done_callback

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

        frame = tk.Frame(master)
        frame.pack(fill="x")

        tk.Button(frame, text="Load Image", command=self.load_image).pack(side="left")
        tk.Button(frame, text="Next", command=self.next_symbol).pack(side="left")

        self.status_var = tk.StringVar()
        tk.Label(master, textvariable=self.status_var).pack(fill="x")

        canvas_frame = tk.Frame(master)
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
        symbol_name = self.symbol_types[self.current_symbol_idx]
        default = self.symbol_defaults[symbol_name]
        symbol = Symbol(symbol_name, (canvas_x, canvas_y), room=None, amperage=default["amperage"], height=default["height"])
        self.annotations.append(symbol)
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
        self.master.destroy()
        self.on_done_callback(self.annotations, self.image_path)

class RoomAnnotator:
    def __init__(self, annotations, image_path):
        self.root = tk.Tk()
        self.root.title("Room Assignment on Hanan Grid")
        self.canvas_frame = tk.Frame(self.root)
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

        self.annotations = annotations  # List[Symbol]
        self.image = Image.open(image_path)
        self.img_tk = ImageTk.PhotoImage(self.image)
        self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)

        

        self.G, self.x_coords, self.y_coords,annotations = annotations_to_hanan_grid(annotations, scale=1, threshold=10)
        self.graph = self.G
        self.symbols = annotations

        self.room_polygons = []  # List of (polygon_points, room_name)
        self.current_polygon = []
        self.dot_room_map = {}  # node -> room_name

        self.canvas.bind("<Button-1>", self.on_click)
        self.finish_button = tk.Button(self.root, text="Finish Room", command=self.finish_room)
        self.finish_button.pack()

        self.roomless_count_label = tk.Label(self.root, text="")
        self.roomless_count_label.pack()

        self.draw_all()
        self.update_roomless_count()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def run(self):
        self.root.mainloop()

    def draw_all(self):
        for x in self.x_coords:
            self.canvas.create_line(x, min(self.y_coords), x, max(self.y_coords), fill="gray", dash=(2, 2))
        for y in self.y_coords:
            self.canvas.create_line(min(self.x_coords), y, max(self.x_coords), y, fill="gray", dash=(2, 2))

        for node in self.G.nodes():
            x, y = node
            color = "red" if self.G.nodes[node].get("is_dot") else "blue"

            # Check if this node corresponds to an electrical panel
            is_panel = any(s.coords == (x, y) and s.name == "electrical panel" for s in self.symbols)

            if is_panel:
                self.canvas.create_rectangle(x-5, y-5, x+5, y+5, fill="black", tags=f"dot_{x}_{y}")
            else:
                self.canvas.create_oval(x-3, y-3, x+3, y+3, fill=color, tags=f"dot_{x}_{y}")


    def update_roomless_count(self):
        roomless = sum(1 for s in self.symbols if s.room is None)
        self.roomless_count_label.config(text=f"Symbols without room: {roomless}")

    def on_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        closest = min(self.G.nodes(), key=lambda n: (n[0]-x)**2 + (n[1]-y)**2)
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

        self.canvas.create_line(self.current_polygon[-1][0], self.current_polygon[-1][1],
                                 self.current_polygon[0][0], self.current_polygon[0][1],
                                 fill="green", width=2)

        room_name = tk.simpledialog.askstring("Room Name", "Enter name for this room:", parent=self.root)
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

    def assign_room_to_dots(self, polygon, room_name):
        poly_path = Path(polygon)
        for node in self.G.nodes():
            if self.G.nodes[node].get("is_dot"):
                if poly_path.contains_point(node, radius=1e-6):
                    self.dot_room_map[node] = room_name
                    self.canvas.itemconfig(f"dot_{node[0]}_{node[1]}", fill="green")
                    self.canvas.create_text(node[0]+5, node[1]-5, text=room_name, fill="black", font=("Arial", 8))

        #Update the rooms in the symbol class and ignore room assignment to electrical panels
        for symbol in self.annotations:
            mapped = (int(symbol.coords[0]), int(symbol.coords[1]))
            if symbol.name != "electrical panel" and mapped in self.dot_room_map and symbol.room is None:
                symbol.room = self.dot_room_map[mapped]



    def assign_room_to_dots(self, polygon, room_name):
        poly_path = Path(polygon)
        for node in self.G.nodes():
            if self.G.nodes[node].get("is_dot"):
                if poly_path.contains_point(node, radius=1e-6):
                    self.dot_room_map[node] = room_name
                    self.canvas.create_text(node[0]+5, node[1]-5, text=room_name, fill="black", font=("Arial", 8))

        for symbol in self.annotations:
            mapped = (int(symbol.coords[0]), int(symbol.coords[1]))
            if mapped in self.dot_room_map and symbol.room is None:
                symbol.room = self.dot_room_map[mapped]

# === WiringVisualizer ===
class WiringVisualizer:
    def __init__(self, symbols, graph, image_path):
        self.symbols = symbols
        self.graph = graph
        self.image_path = image_path
        self.root = tk.Tk()
        self.root.title("Wiring Paths")

        self.canvas_frame = tk.Frame(self.root)
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

        self.image = Image.open(self.image_path)
        self.img_tk = ImageTk.PhotoImage(self.image)
        self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)  # Draw image first

        self.draw_grid()
        self.create_wiring()

        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.root.mainloop()

    def draw_grid(self):
        x_coords = sorted(set(x for x, _ in self.graph.nodes()))
        y_coords = sorted(set(y for _, y in self.graph.nodes()))

        for x in x_coords:
            self.canvas.create_line(x, min(y_coords), x, max(y_coords), fill="gray", dash=(2, 2))
        for y in y_coords:
            self.canvas.create_line(min(x_coords), y, max(x_coords), y, fill="gray", dash=(2, 2))

        for node in self.graph.nodes():
            x, y = node
            color = "red" if self.graph.nodes[node].get("is_dot") else "blue"
            self.canvas.create_oval(x-3, y-3, x+3, y+3, fill=color)
    
    def assign_wire_gauge(self, amperage, length_ft):
        if amperage <= 15:
            return "14 AWG" if length_ft <= 50 else "12 AWG"
        elif amperage <= 20:
            return "12 AWG" if length_ft <= 50 else "10 AWG"
        elif amperage <= 30:
            return "10 AWG" if length_ft <= 50 else "8 AWG"
        else:
            return "Consult engineer"

    def generate_bom(self, scale_factor=0.05):
        bom = defaultdict(list)

        for symbol in self.symbols:
            if symbol.room and symbol.name not in ("junction box", "electrical panel"):
                # Get path to junction
                junction = next((s for s in self.symbols if s.name == "junction box" and s.room == symbol.room), None)
                if not junction:
                    continue

                try:
                    path = nx.shortest_path(self.graph, source=symbol.coords, target=junction.coords)
                except nx.NetworkXNoPath:
                    continue

                # Calculate length in feet
                total_length = sum(
                    ((path[i+1][0]-path[i][0])**2 + (path[i+1][1]-path[i][1])**2)**0.5
                    for i in range(len(path)-1)
                ) * scale_factor

                gauge = self.assign_wire_gauge(float(symbol.amperage), total_length)
                bom[symbol.room].append({
                    "type": symbol.name,
                    "amperage": symbol.amperage,
                    "length_ft": round(total_length, 2),
                    "wire_gauge": gauge
                })

        return bom

    def print_bom(self, scale_factor=0.05):
        bom = self.generate_bom(scale_factor)
        
        print("\n📦 === BILL OF MATERIALS ===")
        for room, items in bom.items():
            print(f"\nRoom: {room}")
            for entry in items:
                print(f" - {entry['type'].capitalize()} | Amps: {entry['amperage']}A | "
                    f"Length: {entry['length_ft']} ft | Wire: {entry['wire_gauge']}")
            
    def create_wiring(self):
        symbols_by_room = defaultdict(list)
        for s in self.symbols:
            if s.room and s.name != "electrical panel":
                symbols_by_room[s.room].append(s)

        paths_by_room = {}

        # === Room Device → Junction Box Paths ===
        for room, devices in symbols_by_room.items():
            junctions = [s for s in devices if s.name == "junction box"]
            if not junctions:
                print(f"⚠️ Room '{room}' has no junction box. Skipping...")
                continue

            junction = junctions[0]
            junction_node = (int(junction.coords[0]), int(junction.coords[1]))

            room_paths = []
            for device in devices:
                if device is junction:
                    continue
                device_node = (int(device.coords[0]), int(device.coords[1]))
                try:
                    path = nx.shortest_path(self.graph, source=device_node, target=junction_node)
                    room_paths.append(path)
                except nx.NetworkXNoPath:
                    print(f"❌ No path between {device_node} and junction in room '{room}'")

            paths_by_room[room] = room_paths

        # === Junction Box → Electrical Panel Paths ===
        panel_symbols = [s for s in self.symbols if s.name == "electrical panel"]
        if panel_symbols:
            panel_node = (int(panel_symbols[0].coords[0]), int(panel_symbols[0].coords[1]))
            panel_paths = []

            for s in self.symbols:
                if s.name == "junction box":
                    junction_node = (int(s.coords[0]), int(s.coords[1]))
                    try:
                        path = nx.shortest_path(self.graph, source=junction_node, target=panel_node)
                        panel_paths.append(path)
                    except nx.NetworkXNoPath:
                        print(f"⚠️ No path from junction at {junction_node} to panel")

            paths_by_room["panel_connections"] = panel_paths
        else:
            print("⚠️ No electrical panel found. Skipping panel connections.")
        self.paths_by_room = paths_by_room 
        self.draw_paths(paths_by_room)
        self.print_bom(scale_factor=0.05)


    def draw_paths(self, paths_by_room):
        colors = ["red", "green", "blue", "orange", "purple", "cyan"]
        for i, (room, paths) in enumerate(paths_by_room.items()):
            color = colors[i % len(colors)]
            for path in paths:
                for j in range(len(path) - 1):
                    x1, y1 = path[j]
                    x2, y2 = path[j + 1]
                    self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2)
        print(f"✅ Wiring paths drawn for rooms: {list(paths_by_room.keys())}")
    

# === Launcher ===
def main():
    result_container = {}

    def start_room_annotator(annotations, image_path):
        app = RoomAnnotator(annotations, image_path)
        app.run()
        result_container["symbols"] = app.symbols
        result_container["graph"] = app.graph

        # Directly launch the wiring visualizer after room annotation
        WiringVisualizer(app.symbols, app.graph,image_path)

    root = tk.Tk()
    app = SymbolAnnotator(root, start_room_annotator)
    root.mainloop()

    # No further processing needed here since wiring is now visualized live
    symbols = result_container.get("symbols")
    graph = result_container.get("graph")

    if symbols is not None and graph is not None:
        print("✅ Data collected after GUI:")
        print(f"- {len(symbols)} symbols")
        print(f"- {len(graph.nodes)} nodes in graph")

if __name__ == "__main__":
    main()

