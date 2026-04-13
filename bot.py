import json
import logging
import os
from datetime import time
from typing import Dict, List

import pandas as pd
from dotenv import load_dotenv
from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackContext,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Загружаем переменные окружения из .env (если файл есть)
load_dotenv()

# Базовая настройка логов
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Имя JSON-файла для хранения данных
DATA_FILE = "contacts.json"
EMPLOYEES_FILE = "employees.csv"

# Состояния для ConversationHandler
ADD_CONTACT_STATE = 1
DELETE_CONTACT_STATE = 2
ADD_REMINDER_STATE = 3
DELETE_REMINDER_STATE = 4
EDIT_CONTACT_SELECT_STATE = 5
EDIT_CONTACT_TEXT_STATE = 6
EMPLOYEE_SEARCH_STATE = 7


def default_user_data() -> Dict[str, object]:
    """Структура данных пользователя по умолчанию."""
    return {
        "contacts": [],
        "reminders": [],
        "digest_enabled": False,
    }


def normalize_user_data(value: object) -> Dict[str, object]:
    """
    Приводит данные пользователя к единому формату.
    Поддерживает старый формат, где user_id -> список контактов.
    """
    if isinstance(value, list):
        return {"contacts": value, "reminders": [], "digest_enabled": False}

    if isinstance(value, dict):
        return {
            "contacts": value.get("contacts", []) if isinstance(value.get("contacts"), list) else [],
            "reminders": value.get("reminders", []) if isinstance(value.get("reminders"), list) else [],
            "digest_enabled": bool(value.get("digest_enabled", False)),
        }

    return default_user_data()


def load_data() -> Dict[str, Dict[str, object]]:
    """Загружает данные из JSON-файла."""
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, dict):
                normalized: Dict[str, Dict[str, object]] = {}
                for user_id, user_data in data.items():
                    normalized[str(user_id)] = normalize_user_data(user_data)
                return normalized
            logger.warning("Неверная структура JSON, используем пустой словарь.")
            return {}
    except (json.JSONDecodeError, OSError) as error:
        logger.error("Ошибка чтения JSON: %s", error)
        return {}


def save_data(data: Dict[str, Dict[str, object]]) -> bool:
    """Сохраняет словарь в JSON-файл."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        return True
    except OSError as error:
        logger.error("Ошибка записи JSON: %s", error)
        return False


def get_user_key(update: Update) -> str:
    """Возвращает user_id строкой для JSON-ключа."""
    return str(update.effective_user.id)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствие и описание возможностей бота."""
    del context
    text = (
        "Привет! Я бот-помощник для команды.\n\n"
        "Что умею:\n"
        "- Отвечать на вопросы о компании/проекте/команде\n"
        "- Хранить личные дела (контакты) коллег\n"
        "- Напоминать о важных событиях\n"
        "- Отправлять ежедневные дайджесты\n\n"
        "Доступные команды:\n"
        "/start — приветствие\n"
        "/add_contact — добавить личное дело коллеги\n"
        "/list_contacts — показать список личных дел\n"
        "/delete — удалить личное дело\n"
        "/edit_contact — изменить личное дело\n"
        "/add_reminder — добавить важное событие\n"
        "/list_reminders — показать важные события\n"
        "/delete_reminder — удалить важное событие\n"
        "/digest_on — включить ежедневный дайджест\n"
        "/digest_off — выключить ежедневный дайджест\n"
        "/employees — поиск сотрудников в employees.csv\n"
        "/company, /project, /team — информация о компании, проекте и команде"
    )
    await update.message.reply_text(text)


async def add_contact_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 1: просим прислать текст личного дела."""
    del context
    await update.message.reply_text("Введите текст личного дела коллеги:")
    return ADD_CONTACT_STATE


async def save_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 2: сохраняем личное дело пользователя."""
    del context
    contact_text = (update.message.text or "").strip()
    if not contact_text:
        await update.message.reply_text("Пустой текст нельзя сохранить. Попробуйте снова.")
        return ADD_CONTACT_STATE

    data = load_data()
    user_key = get_user_key(update)
    user_data = normalize_user_data(data.get(user_key))
    user_contacts = user_data["contacts"]
    user_contacts.append(contact_text)
    user_data["contacts"] = user_contacts
    data[user_key] = user_data

    if save_data(data):
        await update.message.reply_text("Личное дело добавлено.")
    else:
        await update.message.reply_text("Не удалось сохранить данные. Попробуйте позже.")

    return ConversationHandler.END


async def list_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список личных дел текущего пользователя."""
    del context
    data = load_data()
    user_key = get_user_key(update)
    user_contacts = normalize_user_data(data.get(user_key))["contacts"]

    if not user_contacts:
        await update.message.reply_text("Список пуст. Добавьте запись через /add_contact.")
        return

    lines = [f"{index + 1}. {contact}" for index, contact in enumerate(user_contacts)]
    await update.message.reply_text("Ваши личные дела:\n" + "\n".join(lines))


async def delete_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 1 удаления: показываем список и просим номер."""
    del context
    data = load_data()
    user_key = get_user_key(update)
    user_data = normalize_user_data(data.get(user_key))
    user_contacts = user_data["contacts"]

    if not user_contacts:
        await update.message.reply_text("Удалять нечего: список пуст.")
        return ConversationHandler.END

    lines = [f"{index + 1}. {contact}" for index, contact in enumerate(user_contacts)]
    await update.message.reply_text(
        "Какую запись удалить? Отправьте номер:\n" + "\n".join(lines)
    )
    return DELETE_CONTACT_STATE


async def delete_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 2 удаления: удаляем запись по номеру."""
    del context
    data = load_data()
    user_key = get_user_key(update)
    user_data = normalize_user_data(data.get(user_key))
    user_contacts = user_data["contacts"]

    text = (update.message.text or "").strip()
    if not text.isdigit():
        await update.message.reply_text("Нужно отправить номер (например: 1).")
        return DELETE_CONTACT_STATE

    index = int(text) - 1
    if index < 0 or index >= len(user_contacts):
        await update.message.reply_text("Неверный номер. Попробуйте снова.")
        return DELETE_CONTACT_STATE

    deleted_value = user_contacts.pop(index)
    user_data["contacts"] = user_contacts
    data[user_key] = user_data

    if save_data(data):
        await update.message.reply_text(f"Удалено: {deleted_value}")
    else:
        await update.message.reply_text("Не удалось сохранить изменения. Попробуйте позже.")

    return ConversationHandler.END


async def edit_contact_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 1: просим номер контакта для редактирования."""
    data = load_data()
    user_key = get_user_key(update)
    user_data = normalize_user_data(data.get(user_key))
    contacts = user_data["contacts"]

    if not contacts:
        await update.message.reply_text("Редактировать нечего: список контактов пуст.")
        return ConversationHandler.END

    lines = [f"{index + 1}. {item}" for index, item in enumerate(contacts)]
    await update.message.reply_text(
        "Какой контакт изменить? Отправьте номер:\n" + "\n".join(lines)
    )
    return EDIT_CONTACT_SELECT_STATE


async def edit_contact_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 2: запоминаем номер и просим новый текст."""
    text = (update.message.text or "").strip()
    if not text.isdigit():
        await update.message.reply_text("Нужно отправить номер (например: 1).")
        return EDIT_CONTACT_SELECT_STATE

    data = load_data()
    user_key = get_user_key(update)
    contacts = normalize_user_data(data.get(user_key))["contacts"]

    index = int(text) - 1
    if index < 0 or index >= len(contacts):
        await update.message.reply_text("Неверный номер. Попробуйте снова.")
        return EDIT_CONTACT_SELECT_STATE

    context.user_data["edit_contact_index"] = index
    await update.message.reply_text("Введите новый текст для выбранного контакта:")
    return EDIT_CONTACT_TEXT_STATE


async def edit_contact_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 3: сохраняем новый текст контакта."""
    new_text = (update.message.text or "").strip()
    if not new_text:
        await update.message.reply_text("Пустой текст нельзя сохранить. Попробуйте снова.")
        return EDIT_CONTACT_TEXT_STATE

    index = context.user_data.get("edit_contact_index")
    if not isinstance(index, int):
        await update.message.reply_text("Сессия редактирования сброшена. Запустите /edit_contact заново.")
        return ConversationHandler.END

    data = load_data()
    user_key = get_user_key(update)
    user_data = normalize_user_data(data.get(user_key))
    contacts = user_data["contacts"]

    if index < 0 or index >= len(contacts):
        await update.message.reply_text("Контакт не найден. Запустите /edit_contact снова.")
        return ConversationHandler.END

    old_value = contacts[index]
    contacts[index] = new_text
    user_data["contacts"] = contacts
    data[user_key] = user_data
    context.user_data.pop("edit_contact_index", None)

    if save_data(data):
        await update.message.reply_text(f"Контакт обновлен:\nБыло: {old_value}\nСтало: {new_text}")
    else:
        await update.message.reply_text("Не удалось сохранить изменения. Попробуйте позже.")

    return ConversationHandler.END


async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена текущего диалога."""
    del context
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END


async def add_reminder_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 1: просим прислать текст важного события."""
    del context
    await update.message.reply_text("Введите текст важного события (напоминания):")
    return ADD_REMINDER_STATE


async def save_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 2: сохраняем важное событие пользователя."""
    del context
    reminder_text = (update.message.text or "").strip()
    if not reminder_text:
        await update.message.reply_text("Пустой текст нельзя сохранить. Попробуйте снова.")
        return ADD_REMINDER_STATE

    data = load_data()
    user_key = get_user_key(update)
    user_data = normalize_user_data(data.get(user_key))
    reminders = user_data["reminders"]
    reminders.append(reminder_text)
    user_data["reminders"] = reminders
    data[user_key] = user_data

    if save_data(data):
        await update.message.reply_text("Важное событие добавлено.")
    else:
        await update.message.reply_text("Не удалось сохранить данные. Попробуйте позже.")

    return ConversationHandler.END


async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список важных событий текущего пользователя."""
    del context
    data = load_data()
    user_key = get_user_key(update)
    reminders = normalize_user_data(data.get(user_key))["reminders"]

    if not reminders:
        await update.message.reply_text("Список важных событий пуст. Добавьте через /add_reminder.")
        return

    lines = [f"{index + 1}. {item}" for index, item in enumerate(reminders)]
    await update.message.reply_text("Ваши важные события:\n" + "\n".join(lines))


async def delete_reminder_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 1 удаления события: показываем список и просим номер."""
    del context
    data = load_data()
    user_key = get_user_key(update)
    user_data = normalize_user_data(data.get(user_key))
    reminders = user_data["reminders"]

    if not reminders:
        await update.message.reply_text("Удалять нечего: список важных событий пуст.")
        return ConversationHandler.END

    lines = [f"{index + 1}. {item}" for index, item in enumerate(reminders)]
    await update.message.reply_text(
        "Какое важное событие удалить? Отправьте номер:\n" + "\n".join(lines)
    )
    return DELETE_REMINDER_STATE


async def delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 2 удаления события: удаляем по номеру."""
    del context
    data = load_data()
    user_key = get_user_key(update)
    user_data = normalize_user_data(data.get(user_key))
    reminders = user_data["reminders"]

    text = (update.message.text or "").strip()
    if not text.isdigit():
        await update.message.reply_text("Нужно отправить номер (например: 1).")
        return DELETE_REMINDER_STATE

    index = int(text) - 1
    if index < 0 or index >= len(reminders):
        await update.message.reply_text("Неверный номер. Попробуйте снова.")
        return DELETE_REMINDER_STATE

    deleted_value = reminders.pop(index)
    user_data["reminders"] = reminders
    data[user_key] = user_data

    if save_data(data):
        await update.message.reply_text(f"Удалено событие: {deleted_value}")
    else:
        await update.message.reply_text("Не удалось сохранить изменения. Попробуйте позже.")

    return ConversationHandler.END


async def digest_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Включает ежедневный дайджест для пользователя."""
    del context
    data = load_data()
    user_key = get_user_key(update)
    user_data = normalize_user_data(data.get(user_key))
    user_data["digest_enabled"] = True
    data[user_key] = user_data

    if save_data(data):
        await update.message.reply_text("Ежедневный дайджест включен.")
    else:
        await update.message.reply_text("Не удалось сохранить настройки дайджеста.")


async def digest_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выключает ежедневный дайджест для пользователя."""
    del context
    data = load_data()
    user_key = get_user_key(update)
    user_data = normalize_user_data(data.get(user_key))
    user_data["digest_enabled"] = False
    data[user_key] = user_data

    if save_data(data):
        await update.message.reply_text("Ежедневный дайджест выключен.")
    else:
        await update.message.reply_text("Не удалось сохранить настройки дайджеста.")


async def send_daily_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Рассылает ежедневный дайджест пользователям, у кого он включен."""
    data = load_data()

    for user_id, user_data in data.items():
        normalized = normalize_user_data(user_data)
        if not normalized["digest_enabled"]:
            continue

        contacts = normalized["contacts"]
        reminders = normalized["reminders"]

        contacts_block = (
            "\n".join(f"- {item}" for item in contacts[:5]) if contacts else "Нет контактов."
        )
        reminders_block = (
            "\n".join(f"- {item}" for item in reminders[:5]) if reminders else "Нет важных событий."
        )

        digest_text = (
            "Ежедневный дайджест:\n\n"
            "Контакты:\n"
            f"{contacts_block}\n\n"
            "Важные события:\n"
            f"{reminders_block}"
        )

        try:
            await context.bot.send_message(chat_id=int(user_id), text=digest_text)
        except Exception as error:  # noqa: BLE001
            logger.warning("Не удалось отправить дайджест пользователю %s: %s", user_id, error)


async def company_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Информация о компании."""
    del context
    await update.message.reply_text(
        "Компания: внутренний помощник команды. Детали можно уточнить у HR."
    )


async def project_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Информация о проекте."""
    del context
    await update.message.reply_text(
        "Проект: ведем разработку командных инструментов и автоматизаций."
    )


async def team_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Информация о команде."""
    del context
    await update.message.reply_text(
        "Команда: используйте /list_contacts, чтобы увидеть внутренние контакты."
    )


async def answer_team_questions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Простой автоответ на вопросы о компании/проекте/команде."""
    del context
    text = (update.message.text or "").lower()

    if any(keyword in text for keyword in ["компания", "company"]):
        reply = "Компания: внутренний помощник команды. Детали можно уточнить у HR."
    elif any(keyword in text for keyword in ["проект", "project"]):
        reply = "Проект: ведем разработку командных инструментов и автоматизаций."
    elif any(keyword in text for keyword in ["команда", "team"]):
        reply = "Команда: используйте /list_contacts, чтобы увидеть внутренние контакты."
    elif any(keyword in text for keyword in ["напомин", "событ", "дайджест"]):
        reply = (
            "Напоминания и ежедневные дайджесты предусмотрены в базовом виде.\n"
            "Для продакшена добавьте планировщик задач, например APScheduler."
        )
    else:
        reply = (
            "Я могу помочь с контактами коллег и базовыми вопросами о команде.\n"
            "Используйте /start для списка команд."
        )

    await update.message.reply_text(reply)


def load_employees_data() -> pd.DataFrame:
    """
    Загружает CSV с сотрудниками и проверяет обязательные поля.
    Выбрасывает исключения, чтобы обработать их в хендлере.
    """
    if not os.path.exists(EMPLOYEES_FILE):
        raise FileNotFoundError(f"Файл {EMPLOYEES_FILE} не найден.")

    data = pd.read_csv(EMPLOYEES_FILE)
    required_columns = {"name", "department", "role", "email"}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        missing_list = ", ".join(sorted(missing_columns))
        raise ValueError(f"В CSV не хватает колонок: {missing_list}")

    if data.empty:
        raise ValueError("CSV-файл пуст.")

    return data


def format_employee_row(row: pd.Series) -> str:
    """Форматирует строку сотрудника для ответа в Telegram."""
    return (
        f"Имя: {row['name']}\n"
        f"Отдел: {row['department']}\n"
        f"Должность: {row['role']}\n"
        f"Email: {row['email']}"
    )


async def employees_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 1: просим имя сотрудника или название отдела."""
    del context
    await update.message.reply_text(
        "Введите имя сотрудника или отдел для поиска (например, Иван или Marketing):"
    )
    return EMPLOYEE_SEARCH_STATE


async def employees_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 2: ищем сотрудников по имени или отделу в CSV."""
    del context
    query = (update.message.text or "").strip()
    if not query:
        await update.message.reply_text("Пустой запрос. Введите имя или отдел.")
        return EMPLOYEE_SEARCH_STATE

    try:
        employees = load_employees_data()
    except FileNotFoundError:
        await update.message.reply_text(
            f"Файл {EMPLOYEES_FILE} не найден. Добавьте его в папку проекта."
        )
        return ConversationHandler.END
    except (ValueError, pd.errors.EmptyDataError) as error:
        await update.message.reply_text(f"Ошибка данных сотрудников: {error}")
        return ConversationHandler.END
    except Exception as error:  # noqa: BLE001
        logger.exception("Ошибка при чтении employees.csv: %s", error)
        await update.message.reply_text("Не удалось прочитать CSV-файл сотрудников.")
        return ConversationHandler.END

    # Ищем по части имени или отдела, без учета регистра.
    query_lower = query.lower()
    names = employees["name"].astype(str).str.lower()
    departments = employees["department"].astype(str).str.lower()
    result = employees[
        names.str.contains(query_lower, na=False)
        | departments.str.contains(query_lower, na=False)
    ]

    if result.empty:
        await update.message.reply_text("Сотрудники не найдены. Уточните имя или отдел.")
        return ConversationHandler.END

    lines = []
    for _, row in result.iterrows():
        lines.append(format_employee_row(row))

    await update.message.reply_text("Найденные сотрудники:\n\n" + "\n\n".join(lines))
    return ConversationHandler.END


async def error_handler(update: object, context: CallbackContext) -> None:
    """Глобальный обработчик ошибок."""
    # Для сетевых таймаутов даем более понятный ответ.
    # Это частая временная проблема, а не логическая ошибка бота.
    if isinstance(context.error, (TimedOut, NetworkError)):
        logger.warning("Сетевая ошибка Telegram API: %s", context.error)
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "Временная сетевая задержка. Попробуйте команду еще раз."
            )
        return

    logger.exception("Необработанная ошибка: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "Произошла ошибка при обработке запроса. Попробуйте позже."
        )


def main() -> None:
    """Точка входа."""
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError(
            "Переменная TELEGRAM_BOT_TOKEN (или BOT_TOKEN) не найдена в окружении."
        )

    # Увеличиваем таймауты для нестабильной сети.
    app = (
        Application.builder()
        .token(token)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # Диалог добавления (поддерживаем /add_contact и /add)
    add_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("add_contact", add_contact_entry),
            CommandHandler("add", add_contact_entry),
        ],
        states={
            ADD_CONTACT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_contact)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_action)],
    )

    # Диалог удаления
    delete_conversation = ConversationHandler(
        entry_points=[CommandHandler("delete", delete_entry)],
        states={
            DELETE_CONTACT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_contact)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_action)],
    )

    # Диалог редактирования контакта
    edit_contact_conversation = ConversationHandler(
        entry_points=[CommandHandler("edit_contact", edit_contact_entry)],
        states={
            EDIT_CONTACT_SELECT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_contact_select)
            ],
            EDIT_CONTACT_TEXT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_contact_save)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_action)],
    )

    # Диалог добавления события
    reminder_add_conversation = ConversationHandler(
        entry_points=[CommandHandler("add_reminder", add_reminder_entry)],
        states={
            ADD_REMINDER_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_reminder)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_action)],
    )

    # Диалог удаления события
    reminder_delete_conversation = ConversationHandler(
        entry_points=[CommandHandler("delete_reminder", delete_reminder_entry)],
        states={
            DELETE_REMINDER_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_reminder)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_action)],
    )

    # Диалог поиска сотрудников по CSV
    employees_conversation = ConversationHandler(
        entry_points=[CommandHandler("employees", employees_entry)],
        states={
            EMPLOYEE_SEARCH_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, employees_search)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_action)],
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("company", company_info))
    app.add_handler(CommandHandler("project", project_info))
    app.add_handler(CommandHandler("team", team_info))
    app.add_handler(CommandHandler("list_contacts", list_contacts))
    app.add_handler(CommandHandler("list_reminders", list_reminders))
    app.add_handler(CommandHandler("digest_on", digest_on))
    app.add_handler(CommandHandler("digest_off", digest_off))
    app.add_handler(add_conversation)
    app.add_handler(delete_conversation)
    app.add_handler(edit_contact_conversation)
    app.add_handler(reminder_add_conversation)
    app.add_handler(reminder_delete_conversation)
    app.add_handler(employees_conversation)

    # Любой текст без команды трактуем как вопрос к помощнику
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, answer_team_questions))

    # Отправляем дайджест ежедневно в 09:00 по локальному времени сервера.
    if app.job_queue:
        app.job_queue.run_daily(send_daily_digest, time=time(hour=9, minute=0))

    app.add_error_handler(error_handler)

    # Railway mode: запускаем webhook-сервер на порту из окружения.
    port = int(os.getenv("PORT", "8080"))
    webhook_url = os.getenv("WEBHOOK_URL")
    on_railway = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PUBLIC_DOMAIN"))
    if not webhook_url:
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
        if railway_domain:
            webhook_url = f"https://{railway_domain}/webhook"

    if webhook_url:
        logger.info("Бот запущен в webhook-режиме: %s", webhook_url)
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="webhook",
            webhook_url=webhook_url,
            drop_pending_updates=True,
        )
    elif on_railway:
        raise ValueError(
            "Для запуска на Railway нужен WEBHOOK_URL "
            "(или RAILWAY_PUBLIC_DOMAIN для автоформирования URL)."
        )
    else:
        logger.info("WEBHOOK_URL не задан, запускаем polling-режим.")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
