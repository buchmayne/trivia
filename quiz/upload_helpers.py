def get_upload_path(instance, filename):
    """
    Generate a dynamic upload path to S3 based on game number and category.
    Format: game-N/Category_Name/filename.png (for published games)
            drafts/Category_Name/filename.png (for draft games)
    """
    # For Answer model, we need to get the game through the question
    if hasattr(instance, "question"):
        game = instance.question.game if instance.question else None
        category = instance.question.category if instance.question else None
    # For Question model, we can access game directly
    else:
        game = instance.game if hasattr(instance, "game") else None
        category = instance.category if hasattr(instance, "category") else None

    # Determine the prefix based on game state
    if game and game.game_number:
        prefix = f"game-{game.game_number}"
    elif game and game.is_draft:
        prefix = "drafts"
    else:
        prefix = "unknown"

    # Extract the category name (sanitize for filesystem)
    if category:
        category_name = category.name.replace(" ", "_").replace("'", "")
    else:
        category_name = "Unknown"

    path = f"{prefix}/{category_name}/{filename}"

    return path
