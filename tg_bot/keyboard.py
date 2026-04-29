from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def topic_keyboard(topics: list[str]) -> InlineKeyboardMarkup:
    """One button per topic, each on its own row."""
    rows = [
        [InlineKeyboardButton(f"📌 {t[:60]}", callback_data=f"topic:{t[:60]}")]
        for t in topics
    ]
    return InlineKeyboardMarkup(rows)


def post_actions_keyboard(post_index: int, topic: str) -> InlineKeyboardMarkup:
    """Amend / More buttons for a specific post."""
    slug = topic[:50]
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Amend this post", callback_data=f"amend:{post_index}:{slug}"),
            InlineKeyboardButton("💡 More like this", callback_data=f"more:{post_index}:{slug}"),
        ]
    ])


def posts_message(posts: list[str], topic: str) -> tuple[str, InlineKeyboardMarkup]:
    """
    Build a single message text with all 3 posts numbered,
    plus an inline keyboard with Amend/More buttons for each post.
    """
    lines: list[str] = [f"Here are 3 LinkedIn posts for:\n*{topic}*\n"]
    for i, post in enumerate(posts, 1):
        lines.append(f"━━━━━━━━━━ Post {i} ━━━━━━━━━━\n{post}")
    text = "\n\n".join(lines)

    slug = topic[:50]
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✏️ Amend #{i}", callback_data=f"amend:{i-1}:{slug}"),
            InlineKeyboardButton(f"💡 More #{i}", callback_data=f"more:{i-1}:{slug}"),
        ]
        for i in range(1, len(posts) + 1)
    ])
    return text, keyboard
