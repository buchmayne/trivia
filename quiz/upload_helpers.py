def get_upload_path(instance, filename):
    """
    Generate a dynamic upload path to s3 based on game name and category.
    Format: /2025/January/Birds_Eye_View/my_image.png
    """
    # game name is either Month-Year or Future-Game
    game_name = instance.game.name if instance.game else "Unknown"

    if game_name != "Future-Game" and "-" in game_name:
        parts = game_name.split("-")
        if len(parts) == 2:
            month = parts[0]
            year = parts[1]

            prefix = f"{year}/{month}"
    else:
        prefix = "Future-Game"

    # extract the category name
    if instance.category:
        category_name = instance.category.name.replace(" ", "_").replace("'", "")
    else:
        category_name = "Unknown"

    path = f"/{prefix}/{category_name}/{filename}"

    return path
