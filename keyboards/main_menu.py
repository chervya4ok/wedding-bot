from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Основное меню (обычная клавиатура внизу экрана)
main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Чек-лист"), KeyboardButton(text="💰 Бюджет")],
        [KeyboardButton(text="👥 Гости"), KeyboardButton(text="📖 Книга воспоминаний")],
        [KeyboardButton(text="⚙️ Настройки")]
    ],
    resize_keyboard=True
)

# Клавиатура выбора стиля свадьбы при регистрации (обычная клавиатура)
wedding_type_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👰 Классика")],
        [KeyboardButton(text="🌿 На природе")],
        [KeyboardButton(text="🏙️ Лофт/город")],
        [KeyboardButton(text="🎭 Тематическая")],
        [KeyboardButton(text="Другое")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Инлайн-клавиатура для выбора стиля при редактировании (под сообщением)
def get_wedding_type_inline_keyboard():
    """Инлайн-клавиатура для выбора стиля свадьбы при редактировании"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👰 Классика", callback_data="wedding_type_edit_классика"),
            InlineKeyboardButton(text="🌿 На природе", callback_data="wedding_type_edit_на природе")
        ],
        [
            InlineKeyboardButton(text="🏙️ Лофт/город", callback_data="wedding_type_edit_лофт"),
            InlineKeyboardButton(text="🎭 Тематическая", callback_data="wedding_type_edit_тематическая")
        ],
        [
            InlineKeyboardButton(text="✏️ Другое", callback_data="wedding_type_edit_другое")
        ],
        [
            InlineKeyboardButton(text="⬅️ Отмена", callback_data="settings_back")
        ]
        # В клавиатуре добавьте:
[
    InlineKeyboardButton(
        text="📤 Отправить напрямую",
        switch_inline_query_current_chat=f"Привет! Присоединяйся к нашей свадьбе: {invite_link}"
    )
]
    ])