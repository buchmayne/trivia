def get_upload_path(instance, filename):
    """
    Generate a dynamic upload path to s3 based on game name and category.
    Format: /2025/January/Birds_Eye_View/my_image.png
    """
    # For Answer model, we need to get the game through the question
    if hasattr(instance, 'question'):
        game = instance.question.game if instance.question else None
        category = instance.question.category if instance.question else None
    # For Question model, we can access game directly
    else:
        game = instance.game if hasattr(instance, 'game') else None
        category = instance.category if hasattr(instance, 'category') else None
    
    # game name is either Month-Year or Future-Game
    game_name = game.name if game else "Unknown"

    if game_name != "Future-Game" and "-" in game_name:
        parts = game_name.split("-")
        if len(parts) == 2:
            month = parts[0]
            year = parts[1]

            prefix = f"{year}/{month}"
    else:
        prefix = "Future-Games"

    # extract the category name
    if category:
        category_name = category.name.replace(" ", "_").replace("'", "")
    else:
        category_name = "Unknown"

    path = f"{prefix}/{category_name}/{filename}"

    return path
