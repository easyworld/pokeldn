def generate_unique_id(route):
    return getattr(route, "name", "")
