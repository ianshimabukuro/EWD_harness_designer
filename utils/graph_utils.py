import matplotlib.pyplot as plt
import networkx as nx

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
