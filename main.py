import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import json

# Setup
symbol_types = ["outlet", "switch"]
current_symbol_idx = 0
annotations = {symbol: [] for symbol in symbol_types}
img_tk = None

def load_image():
    global img_tk, image_path
    image_path = filedialog.askopenfilename()
    if not image_path:
        return

    img = Image.open(image_path)
    img_tk = ImageTk.PhotoImage(img)

    canvas.config(scrollregion=(0, 0, img_tk.width(), img_tk.height()))
    canvas.create_image(0, 0, anchor="nw", image=img_tk)
    update_status()

def click_event(event):
    canvas_x = canvas.canvasx(event.x)
    canvas_y = canvas.canvasy(event.y)

    symbol = symbol_types[current_symbol_idx]
    annotations[symbol].append({"x": canvas_x, "y": canvas_y})
    canvas.create_oval(canvas_x-3, canvas_y-3, canvas_x+3, canvas_y+3, fill="red")
    print(f"{symbol} marked at ({canvas_x}, {canvas_y})")

def next_symbol():
    global current_symbol_idx
    if current_symbol_idx + 1 < len(symbol_types):
        current_symbol_idx += 1
        update_status()
    else:
        status_var.set("Annotation complete. You can now save.")

def update_status():
    current = symbol_types[current_symbol_idx]
    status_var.set(f"Select all {current}s where they meet the wall, then click 'Next'")

def save_annotations():
    if not img_tk:
        return
    output_name = "annotations.json"
    with open(output_name, "w") as f:
        json.dump(annotations, f, indent=2)
    print(f"Annotations saved to {output_name}")

# === GUI ===
root = tk.Tk()
root.title("Electrical Plan Annotator")

frame = tk.Frame(root)
frame.pack(fill="x")

tk.Button(frame, text="Load Image", command=load_image).pack(side="left")
tk.Button(frame, text="Next", command=next_symbol).pack(side="left")
tk.Button(frame, text="Save", command=save_annotations).pack(side="left")

status_var = tk.StringVar()
status_label = tk.Label(root, textvariable=status_var, fg="blue")
status_label.pack(fill="x")

canvas_frame = tk.Frame(root)
canvas_frame.pack(fill="both", expand=True)

h_scroll = tk.Scrollbar(canvas_frame, orient="horizontal")
h_scroll.pack(side="bottom", fill="x")

v_scroll = tk.Scrollbar(canvas_frame, orient="vertical")
v_scroll.pack(side="right", fill="y")

canvas = tk.Canvas(canvas_frame, xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set, bg="white")
canvas.pack(side="left", fill="both", expand=True)

h_scroll.config(command=canvas.xview)
v_scroll.config(command=canvas.yview)

canvas.bind("<Button-1>", click_event)

root.mainloop()
