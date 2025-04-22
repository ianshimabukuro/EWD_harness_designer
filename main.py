# main.py

import tkinter as tk
from symbol_annotator import SymbolAnnotator
from room_annotator import RoomAnnotator
from wiring_visualizer import WiringVisualizer
from graph_utils import draw_paths_on_grid  # optional: for matplotlib plotting


def main():
    root = tk.Tk()
    root.title("Electrical Planner")
    root.geometry("1400x900")  

    container = {} 

    # === Step 3: WiringVisualizer ===
    def start_wiring_visualizer(container):
        clear_window()
        wiring_frame = WiringVisualizer(root,container)
        wiring_frame.pack(fill="both", expand=True)

    # === Step 2: RoomAnnotator ===
    def start_room_annotator(container):
        clear_window()
        room_frame = RoomAnnotator(root, container, on_done=start_wiring_visualizer)
        room_frame.pack(fill="both", expand=True)

    # === Step 1: SymbolAnnotator ===
    def start_symbol_annotator():
        symbol_frame = SymbolAnnotator(root,container,on_done=start_room_annotator)
        symbol_frame.pack(fill="both", expand=True)

    # Helper to remove previous frame widgets
    def clear_window():
        for widget in root.winfo_children():
            widget.pack_forget()

    # Start the GUI app
    start_symbol_annotator()
    root.mainloop()

if __name__ == "__main__":
    main()

