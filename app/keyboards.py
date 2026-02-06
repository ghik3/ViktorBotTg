from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🆘 Создать обращение")],
            [KeyboardButton(text="📚 FAQ"), KeyboardButton(text="📜 Правила")],
            [KeyboardButton(text="📌 Статус заявки"), KeyboardButton(text="👤 Позвать оператора")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие…"
    )

def back_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ В меню")]],
        resize_keyboard=True
    )

def admin_ticket_kb(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Закрыть", callback_data=f"tclose:{ticket_id}"),
                InlineKeyboardButton(text="🧹 Удалить", callback_data=f"tdelete:{ticket_id}")
            ]
        ]
    )
