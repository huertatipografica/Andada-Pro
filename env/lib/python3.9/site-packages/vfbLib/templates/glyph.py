def get_empty_glyph(num_masters: int):
    return {
        "metrics": [(0, 0) for _ in range(num_masters)],
        "name": "",
        "nodes": [],
        "num_masters": num_masters,
    }
