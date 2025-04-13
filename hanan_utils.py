import networkx as nx

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