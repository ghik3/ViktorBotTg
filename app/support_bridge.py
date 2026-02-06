# Связь: message_id (сообщение у админа) -> ticket_id
# Хранится в памяти процесса. После перезапуска бота связи сбросятся.
ADMIN_MSG_TO_TICKET: dict[int, int] = {}
