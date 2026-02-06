# app/support_bridge.py
# Связь: message_id (сообщение у админа) -> ticket_id
# Хранится в памяти процесса (после перезапуска связи сбросятся — это нормально)
ADMIN_MSG_TO_TICKET: dict[int, int] = {}
