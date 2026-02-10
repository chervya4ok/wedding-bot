import secrets  # Для генерации безопасных токенов
import logging
import uuid  # ← ДОБАВЬТЕ ЭТУ СТРОКУ
import uuid  # Для генерации уникальных ID инлайн-результатов
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, 
    BufferedInputFile, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards.main_menu import main_menu_keyboard, wedding_type_keyboard, get_wedding_type_inline_keyboard
from database.db import AsyncSessionLocal
from database.models import Couple, Task, Expense, Guest, Memory
from sqlalchemy import select
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)
router = Router()

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
async def get_couple_by_chat_id(chat_id: int):
    """Получить пару по chat_id любого из партнёров (основного или второго)"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Couple).where(
                (Couple.chat_id == chat_id) | 
                (Couple.partner_chat_id == chat_id)
            )
        )
        return result.scalar_one_or_none()

# === СОСТОЯНИЯ ===
class TaskEditStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_date = State()
    waiting_for_new_task_title = State()
    waiting_for_new_task_date = State()

class BudgetStates(StatesGroup):
    waiting_for_expense = State()
    waiting_for_expense_description = State()

class GuestStates(StatesGroup):
    waiting_for_guest_name = State()
    waiting_for_guest_contact = State()
    waiting_for_guest_notes = State()
    waiting_for_plus_one_name = State()

class MemoryStates(StatesGroup):
    waiting_for_answer = State()

class SettingsStates(StatesGroup):
    waiting_for_wedding_date_edit = State()
    waiting_for_partner_names_edit = State()
    waiting_for_budget_edit = State()
    waiting_for_wedding_type_edit = State()

class RegistrationStates(StatesGroup):
    waiting_for_wedding_date = State()
    waiting_for_partner_names = State()
    waiting_for_wedding_type = State()
    waiting_for_budget = State()

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def get_checklist_keyboard(tasks):
    buttons = []
    for task in tasks:
        status_emoji = "✅" if task.is_completed else "⏳"
        title = task.title if len(task.title) <= 25 else task.title[:22] + "..."
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_emoji} {title}",
                callback_data=f"task_detail_{task.id}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="📥 Скачать отчёт (PDF)", callback_data="export_pdf"),
        InlineKeyboardButton(text="➕ Добавить задачу", callback_data="task_add")
    ])
    buttons.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data="checklist_refresh")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_task_detail_keyboard(task_id: int, is_completed: bool, category: str = None):
    status_text = "↩️ Отменить" if is_completed else "✅ Выполнено"
    keyboard = [
        [
            InlineKeyboardButton(text=status_text, callback_data=f"task_toggle_{task_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"task_edit_{task_id}")
        ],
    ]
    if category and category in ["локация", "фото", "платье", "костюм", "декор", "еда", "музыка", "транспорт"]:
        keyboard.append([
            InlineKeyboardButton(text="💰 Добавить трату", callback_data=f"quick_expense_{task_id}_{category}")
        ])
    if "приглашен" in category or category == "гости":
        keyboard.append([
            InlineKeyboardButton(text="👥 Управление гостями", callback_data="guests_list_from_task")
        ])
    keyboard.append([
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"task_delete_confirm_{task_id}")
    ])
    keyboard.append([
        InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="checklist_back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_task_edit_keyboard(task_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Название", callback_data=f"task_edit_field_{task_id}_title"),
            InlineKeyboardButton(text="📅 Дата", callback_data=f"task_edit_field_{task_id}_date")
        ],
        [
            InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"task_detail_{task_id}")
        ]
    ])

def get_task_delete_confirm_keyboard(task_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"task_delete_{task_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"task_detail_{task_id}")
        ]
    ])

def get_budget_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить трату", callback_data="budget_add_expense")
        ],
        [
            InlineKeyboardButton(text="📊 По категориям", callback_data="budget_by_category"),
            InlineKeyboardButton(text="📈 История трат", callback_data="budget_history")
        ],
        [
            InlineKeyboardButton(text="📥 Скачать отчёт (PDF)", callback_data="export_pdf"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="budget_refresh")
        ]
    ])

def get_expense_category_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📸 Фото/Видео", callback_data="expense_cat_фото"),
            InlineKeyboardButton(text="🏛️ Локация", callback_data="expense_cat_локация")
        ],
        [
            InlineKeyboardButton(text="👗 Платье", callback_data="expense_cat_платье"),
            InlineKeyboardButton(text="🤵 Костюм", callback_data="expense_cat_костюм")
        ],
        [
            InlineKeyboardButton(text="🎨 Декор", callback_data="expense_cat_декор"),
            InlineKeyboardButton(text="🍇 Еда/Напитки", callback_data="expense_cat_еда")
        ],
        [
            InlineKeyboardButton(text="✉️ Приглашения", callback_data="expense_cat_гости"),
            InlineKeyboardButton(text="🎵 Музыка", callback_data="expense_cat_музыка")
        ],
        [
            InlineKeyboardButton(text="🚕 Транспорт", callback_data="expense_cat_транспорт"),
            InlineKeyboardButton(text="🎁 Прочее", callback_data="expense_cat_организация")
        ],
        [
            InlineKeyboardButton(text="⬅️ Отмена", callback_data="budget_back")
        ]
    ])

def format_currency(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", " ")

def create_progress_bar(percent: float, length: int = 15) -> str:
    filled = int(length * percent / 100)
    empty = length - filled
    bar = "█" * filled + "░" * empty
    return f"{bar} {percent:.0f}%"

def get_guests_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить гостя", callback_data="guests_add")
        ],
        [
            InlineKeyboardButton(text="👥 Список гостей", callback_data="guests_list"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="guests_stats")
        ],
        [
            InlineKeyboardButton(text="📥 Скачать отчёт (PDF)", callback_data="export_pdf"),
            InlineKeyboardButton(text="✉️ Разослать приглашения", callback_data="guests_invite_all")
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="guests_refresh")
        ]
    ])

def get_guest_detail_keyboard(guest_id: int, is_confirmed: bool, will_not_come: bool):
    buttons = []
    if not is_confirmed and not will_not_come:
        buttons.append([
            InlineKeyboardButton(text="✅ Подтвердить участие", callback_data=f"guest_confirm_{guest_id}"),
            InlineKeyboardButton(text="❌ Не придёт", callback_data=f"guest_decline_{guest_id}")
        ])
    elif is_confirmed:
        buttons.append([
            InlineKeyboardButton(text="↩️ Отменить подтверждение", callback_data=f"guest_unconfirm_{guest_id}")
        ])
    buttons.append([
        InlineKeyboardButton(text="➕ Добавить +1", callback_data=f"guest_add_plus_one_{guest_id}")
    ])
    buttons.append([
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"guest_edit_{guest_id}"),
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"guest_delete_confirm_{guest_id}")
    ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="guests_list")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def format_guest_status(guest) -> str:
    if guest.will_not_come:
        return "❌ Не придёт"
    elif guest.is_confirmed:
        status = "✅ Подтверждён"
        if guest.has_plus_one:
            status += f" (+1: {guest.plus_one_name or 'не указано'})"
        return status
    else:
        return "⏳ Ожидает ответа"

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, command: Command = None):
    """Единый обработчик /start с поддержкой приглашений партнёра и гостей"""
    # === ОБРАБОТКА ПРИГЛАШЕНИЯ ПАРТНЁРА (share_) ===
    if command and command.args and command.args.startswith("share_"):
        share_token = command.args.split("_", 1)[1].strip()
        logger.info(f"📥 Получен токен приглашения партнёра: {share_token} от пользователя {message.chat.id}")
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Couple).where(Couple.share_token == share_token)
            )
            couple = result.scalar_one_or_none()
            
            if not couple:
                logger.warning(f"❌ Токен {share_token} не найден в БД или уже использован")
                await message.answer(
                    "❌ Ссылка недействительна или уже использована.\n"
                    "Попросите партнёра сгенерировать новую ссылку.",
                    reply_markup=main_menu_keyboard
                )
                return
            
            # Проверяем, не является ли этот пользователь уже основным партнёром
            if couple.chat_id == message.chat.id:
                logger.info(f"ℹ️ Пользователь {message.chat.id} уже является основным партнёром")
                await message.answer(
                    f"Вы уже владелец свадьбы {couple.partner1_name} и {couple.partner2_name}!",
                    reply_markup=main_menu_keyboard
                )
                return
            
            # Проверяем, не привязан ли уже второй партнёр
            if couple.partner_chat_id:
                if couple.partner_chat_id == message.chat.id:
                    logger.info(f"ℹ️ Пользователь {message.chat.id} уже привязан к свадьбе")
                    await message.answer(
                        f"✅ Вы уже привязаны к свадьбе {couple.partner1_name} и {couple.partner2_name}!",
                        reply_markup=main_menu_keyboard
                    )
                else:
                    logger.warning(f"⚠️ К свадьбе {couple.id} уже привязан другой партнёр (chat_id={couple.partner_chat_id})")
                    await message.answer(
                        "❌ К этой свадьбе уже привязан другой партнёр.",
                        reply_markup=main_menu_keyboard
                    )
                return
            
            # Привязываем второго партнёра
            logger.info(f"✅ Привязываем партнёра {message.chat.id} к свадьбе {couple.id}")
            couple.partner_chat_id = message.chat.id
            couple.share_token = None  # Аннулируем токен после использования
            await session.commit()
            
            # Уведомляем основного партнёра
            try:
                await message.bot.send_message(
                    chat_id=couple.chat_id,
                    text=f"✅ {couple.partner2_name} присоединился(ась) к вашей свадьбе!\n"
                         f"Теперь вы оба можете управлять чек-листом, бюджетом и гостями."
                )
                logger.info(f"📤 Уведомление отправлено основному партнёру {couple.chat_id}")
            except Exception as e:
                logger.error(f"❌ Не удалось отправить уведомление: {e}")
            
            await message.answer(
                f"✅ Добро пожаловать, {couple.partner2_name}!\n\n"
                f"Вы присоединились к свадьбе {couple.partner1_name} и {couple.partner2_name}.\n"
                f"Теперь вы оба можете управлять подготовкой к свадьбе в этом боте!",
                reply_markup=main_menu_keyboard
            )
            return
    
    # === ОБРАБОТКА ПРИГЛАШЕНИЯ ГОСТЯ (guest_) ===
    if command and command.args and command.args.startswith("guest_"):
        guest_id = int(command.args.split("_", 1)[1].strip())
        logger.info(f"📥 Получен запрос на подтверждение гостя ID {guest_id} от пользователя {message.chat.id}")
        
        async with AsyncSessionLocal() as session:
            guest = await session.get(Guest, guest_id)
            if not guest:
                await message.answer(
                    "❌ Приглашение недействительно.\n"
                    "Возможно, гость был удалён из списка.",
                    reply_markup=main_menu_keyboard
                )
                return
            
            couple = await session.get(Couple, guest.couple_id)
            if not couple:
                await message.answer(
                    "❌ Ошибка: свадьба не найдена.",
                    reply_markup=main_menu_keyboard
                )
                return
            
            # Проверяем, не подтверждён ли уже гость
            if guest.is_confirmed:
                await message.answer(
                    f"✅ Вы уже подтвердили участие в свадьбе {couple.partner1_name} и {couple.partner2_name}!",
                    reply_markup=main_menu_keyboard
                )
                return
            
            if guest.will_not_come:
                await message.answer(
                    f"❌ Вы ранее отказались от участия в свадьбе {couple.partner1_name} и {couple.partner2_name}.",
                    reply_markup=main_menu_keyboard
                )
                return
            
            # Подтверждаем участие гостя
            guest.is_confirmed = True
            guest.will_not_come = False
            await session.commit()
            
            # Уведомляем пару
            try:
                await message.bot.send_message(
                    chat_id=couple.chat_id,
                    text=f"🎉 Гость {guest.name} подтвердил(а) участие в вашей свадьбе!"
                )
                if couple.partner_chat_id:
                    await message.bot.send_message(
                        chat_id=couple.partner_chat_id,
                        text=f"🎉 Гость {guest.name} подтвердил(а) участие в вашей свадьбе!"
                    )
            except:
                pass
            
            await message.answer(
                f"✅ Спасибо, {guest.name}!\n\n"
                f"Вы подтвердили участие в свадьбе:\n"
                f"👰🤵 {couple.partner1_name} и {couple.partner2_name}\n"
                f"📅 {couple.wedding_date.strftime('%d.%m.%Y')}\n\n"
                f"Если ваши планы изменятся, сообщите об этом паре напрямую.",
                reply_markup=main_menu_keyboard
            )
            return
    
    # === СТАНДАРТНАЯ РЕГИСТРАЦИЯ / ВХОД ===
    couple = await get_couple_by_chat_id(message.chat.id)
    
    if couple:
        days_left = (couple.wedding_date - datetime.now().date()).days
        await message.answer(
            f"С возвращением, {couple.partner1_name} и {couple.partner2_name}! 👰🤵\n\n"
            f"Ваша свадьба: {couple.wedding_date.strftime('%d.%m.%Y')}\n"
            f"До свадьбы: {days_left} дней\n\n"
            f"Чем могу помочь сегодня?",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
    else:
        await message.answer(
            "🎉 Привет! Я — ваш личный помощник по подготовке к свадьбе!\n\n"
            "Я помогу вам:\n"
            "✅ Следить за чек-листом задач\n"
            "✅ Контролировать бюджет без ссор\n"
            "✅ Организовать гостей без стресса\n"
            "✅ Получать ежедневную мотивацию и поддержку 😊\n\n"
            "Давайте начнём! Когда у вас свадьба?\n"
            "Напишите дату в формате: ДД.ММ.ГГГГ (например: 15.09.2026)"
        )
        await state.set_state(RegistrationStates.waiting_for_wedding_date)

@router.message(RegistrationStates.waiting_for_wedding_date)
async def process_wedding_date(message: Message, state: FSMContext):
    try:
        date_text = message.text.strip()
        for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
            try:
                wedding_date = datetime.strptime(date_text, fmt).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError("Неверный формат")
        
        if wedding_date <= datetime.now().date():
            await message.answer("❌ Дата свадьбы должна быть в будущем! Попробуйте ещё раз:")
            return
        
        await state.update_data(wedding_date=wedding_date)
        days_until = (wedding_date - datetime.now().date()).days
        
        await message.answer(
            f"Отлично! До свадьбы {days_until} дней — идеально для подготовки! 💫\n\n"
            "Теперь напишите имена вас и вашего партнёра через 'и':\n"
            "Пример: Алексей и Анна"
        )
        await state.set_state(RegistrationStates.waiting_for_partner_names)
        
    except Exception:
        await message.answer("❌ Неверный формат даты! Напишите: ДД.ММ.ГГГГ (например: 15.09.2026)")

@router.message(RegistrationStates.waiting_for_partner_names)
async def process_partner_names(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    
    if " и " not in text:
        await message.answer("❌ Напишите два имени через 'и' (пример: Иван и Мария)")
        return
    
    names = [n.strip().capitalize() for n in text.split(" и ")]
    if len(names) != 2:
        await message.answer("❌ Напишите ровно два имени через 'и'")
        return
    
    partner1, partner2 = names
    
    await state.update_data(partner1_name=partner1, partner2_name=partner2)
    
    await message.answer(
        f"Прекрасно, {partner1} и {partner2}! 👰🤵\n\n"
        "Какая у вас свадьба?",
        reply_markup=wedding_type_keyboard
    )
    await state.set_state(RegistrationStates.waiting_for_wedding_type)

@router.message(RegistrationStates.waiting_for_wedding_type)
async def process_wedding_type(message: Message, state: FSMContext):
    wedding_type_map = {
        "👰 Классика": "классика",
        "🌿 На природе": "на природе",
        "🏙️ Лофт/город": "лофт",
        "🎭 Тематическая": "тематическая",
        "Другое": "другое"
    }
    
    wedding_type = wedding_type_map.get(message.text, message.text)
    await state.update_data(wedding_type=wedding_type)
    
    await message.answer(
        f"Стиль '{wedding_type}' — будет красиво! ✨\n\n"
        "Какой у вас бюджет на свадьбу?\n"
        "Напишите сумму в рублях (пример: 500000)"
    )
    await state.set_state(RegistrationStates.waiting_for_budget)

@router.message(RegistrationStates.waiting_for_budget)
async def process_budget(message: Message, state: FSMContext):
    try:
        budget_text = re.sub(r"[^\d.]", "", message.text)
        budget = float(budget_text)
        
        if budget <= 0:
            await message.answer("❌ Бюджет должен быть положительным! Попробуйте ещё раз:")
            return
        
        if budget < 10000:
            await message.answer("❌ Такой бюджет маловат для свадьбы 😅 Укажите реальную сумму:")
            return
        
        await state.update_data(budget_total=budget)
        data = await state.get_data()
        
        async with AsyncSessionLocal() as session:
            couple = Couple(
                chat_id=message.chat.id,
                partner1_name=data["partner1_name"],
                partner2_name=data["partner2_name"],
                wedding_date=data["wedding_date"],
                wedding_type=data["wedding_type"],
                budget_total=budget,
                created_at=datetime.now().date()
            )
            session.add(couple)
            await session.commit()
            await session.refresh(couple)
            
            await create_default_tasks(session, couple.id, data["wedding_date"], budget)
            await session.commit()
        
        await message.answer(
            f"🎊 Ура! Регистрация завершена!\n\n"
            f"👰🤵 {data['partner1_name']} и {data['partner2_name']}\n"
            f"📅 Свадьба: {data['wedding_date'].strftime('%d.%m.%Y')}\n"
            f"💫 Стиль: {data['wedding_type']}\n"
            f"💰 Бюджет: {budget:,.0f} ₽\n\n"
            f"Я уже создал для вас персональный чек-лист задач! 📝\n"
            f"Нажмите кнопку «📝 Чек-лист» ниже, чтобы посмотреть.",
            reply_markup=main_menu_keyboard
        )
        
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}\nПопробуйте ещё раз:")

async def create_default_tasks(session, couple_id: int, wedding_date, budget_total: float):
    tasks_config = [
        {"title": "Забронировать локацию", "category": "локация", "days_before": 180},
        {"title": "Выбрать фотографа", "category": "фото", "days_before": 120},
        {"title": "Заказать платье", "category": "платье", "days_before": 120},
        {"title": "Заказать костюм", "category": "костюм", "days_before": 90},
        {"title": "Отправить приглашения", "category": "гости", "days_before": 60},
        {"title": "Забронировать декор", "category": "декор", "days_before": 60},
        {"title": "Заказать торт и банкет", "category": "еда", "days_before": 30},
        {"title": "Финальная примерка", "category": "платье", "days_before": 14},
        {"title": "Подтвердить все детали", "category": "организация", "days_before": 7},
    ]
    
    for task in tasks_config:
        due_date = wedding_date - timedelta(days=task["days_before"])
        
        if due_date >= datetime.now().date():
            new_task = Task(
                couple_id=couple_id,
                title=task["title"],
                category=task["category"],
                due_date=due_date,
                days_before_wedding=None,
                is_completed=False
            )
            session.add(new_task)

# === ЧЕК-ЛИСТ ===
@router.message(F.text == "📝 Чек-лист")
async def show_checklist(message: Message):
    couple = await get_couple_by_chat_id(message.chat.id)
    
    if not couple:
        await message.answer("Сначала зарегистрируйтесь через /start")
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Task)
            .where(Task.couple_id == couple.id)
            .order_by(Task.due_date)
        )
        tasks = result.scalars().all()
        
        if not tasks:
            await message.answer(
                "📋 У вас пока нет задач!\n"
                "Нажмите «➕ Добавить задачу», чтобы создать первую.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить задачу", callback_data="task_add")]
                ])
            )
            return
        
        text = "📋 <b>Ваш чек-лист подготовки:</b>\n\n"
        today = datetime.now().date()
        
        for i, task in enumerate(tasks, 1):
            status = "✅" if task.is_completed else "⏳"
            due_date = task.due_date.strftime("%d.%m")
            days_left = (task.due_date - today).days
            
            if days_left < 0:
                days_info = "❗ ПРОСРОЧЕНО"
            elif days_left == 0:
                days_info = "СЕГОДНЯ"
            elif days_left <= 3:
                days_info = f"через {days_left} дн."
            else:
                days_info = f"осталось {days_left} дн."
            
            text += f"{i}. {status} <b>{task.title}</b>\n"
            text += f"   📅 {due_date} ({days_info})\n"
            text += f"   🏷️ {task.category.capitalize()}\n\n"
        
        total = len(tasks)
        completed = sum(1 for t in tasks if t.is_completed)
        progress = int(completed / total * 100)
        text += f"\n📊 Прогресс: {completed}/{total} ({progress}%)"
        
        await message.answer(
            text,
            reply_markup=get_checklist_keyboard(tasks),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "checklist_refresh")
async def refresh_checklist(callback: CallbackQuery):
    await callback.answer("🔄 Обновляю...")
    await show_checklist(callback.message)

@router.callback_query(F.data == "checklist_back")
async def back_to_checklist(callback: CallbackQuery):
    await callback.answer()
    await show_checklist(callback.message)

@router.callback_query(F.data.startswith("task_detail_"))
async def show_task_detail(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        task = await session.get(Task, task_id)
        if not task:
            await callback.answer("Задача не найдена!", show_alert=True)
            return
        
        today = datetime.now().date()
        days_left = (task.due_date - today).days
        
        if days_left < 0:
            days_info = "❗ ПРОСРОЧЕНО"
            emoji = "🔥"
        elif days_left == 0:
            days_info = "СЕГОДНЯ"
            emoji = "💥"
        elif days_left <= 3:
            days_info = f"через {days_left} дн."
            emoji = "⚠️"
        else:
            days_info = f"осталось {days_left} дн."
            emoji = "📅"
        
        status_text = "✅ ВЫПОЛНЕНО" if task.is_completed else "⏳ В ПРОЦЕССЕ"
        
        text = f"<b>{task.title}</b>\n\n"
        text += f"Статус: {status_text}\n"
        text += f"{emoji} Дедлайн: {task.due_date.strftime('%d.%m.%Y')} ({days_info})\n"
        text += f"🏷️ Категория: {task.category.capitalize()}"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_task_detail_keyboard(task.id, task.is_completed, task.category),
            parse_mode="HTML"
        )
        await callback.answer()

@router.callback_query(F.data.startswith("task_toggle_"))
async def toggle_task_status(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        task = await session.get(Task, task_id)
        if not task:
            await callback.answer("Задача не найдена!", show_alert=True)
            return
        
        task.is_completed = not task.is_completed
        await session.commit()
        
        status = "✅ выполнена" if task.is_completed else "↩️ отменена"
        await callback.answer(f"Задача {status}!", show_alert=True)
        
        today = datetime.now().date()
        days_left = (task.due_date - today).days
        
        if days_left < 0:
            days_info = "❗ ПРОСРОЧЕНО"
            emoji = "🔥"
        elif days_left == 0:
            days_info = "СЕГОДНЯ"
            emoji = "💥"
        elif days_left <= 3:
            days_info = f"через {days_left} дн."
            emoji = "⚠️"
        else:
            days_info = f"осталось {days_left} дн."
            emoji = "📅"
        
        status_text = "✅ ВЫПОЛНЕНО" if task.is_completed else "⏳ В ПРОЦЕССЕ"
        
        text = f"<b>{task.title}</b>\n\n"
        text += f"Статус: {status_text}\n"
        text += f"{emoji} Дедлайн: {task.due_date.strftime('%d.%m.%Y')} ({days_info})\n"
        text += f"🏷️ Категория: {task.category.capitalize()}"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_task_detail_keyboard(task.id, task.is_completed, task.category),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("task_edit_"))
async def start_task_edit(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[2])
    await callback.message.edit_reply_markup(reply_markup=get_task_edit_keyboard(task_id))
    await callback.answer()

@router.callback_query(F.data.startswith("task_edit_field_"))
async def edit_task_field(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    task_id = int(parts[3])
    field = parts[4]
    
    if field == "title":
        await state.update_data(editing_task_id=task_id, editing_field="title")
        await callback.message.edit_text(
            "✏️ Введите новое название задачи:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"task_detail_{task_id}")]
            ])
        )
        await state.set_state(TaskEditStates.waiting_for_title)
        
    elif field == "date":
        await state.update_data(editing_task_id=task_id, editing_field="date")
        await callback.message.edit_text(
            "📅 Введите новую дату дедлайна (ДД.ММ.ГГГГ):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"task_detail_{task_id}")]
            ])
        )
        await state.set_state(TaskEditStates.waiting_for_date)
    
    await callback.answer()

@router.message(TaskEditStates.waiting_for_title)
async def process_new_title(message: Message, state: FSMContext):
    new_title = message.text.strip()
    
    if len(new_title) < 3:
        await message.answer("❌ Название должно быть от 3 символов. Попробуйте ещё раз:")
        return
    
    data = await state.get_data()
    task_id = data["editing_task_id"]
    
    async with AsyncSessionLocal() as session:
        task = await session.get(Task, task_id)
        if task:
            old_title = task.title
            task.title = new_title
            await session.commit()
            await message.answer(
                f"✅ Задача «{old_title}» переименована в «{new_title}»",
                reply_markup=main_menu_keyboard
            )
        else:
            await message.answer("❌ Задача не найдена", reply_markup=main_menu_keyboard)
    
    await state.clear()
    await show_checklist(message)

@router.message(TaskEditStates.waiting_for_date)
async def process_new_date(message: Message, state: FSMContext):
    try:
        date_text = message.text.strip()
        for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
            try:
                new_date = datetime.strptime(date_text, fmt).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError("Неверный формат")
        
        if new_date < datetime.now().date():
            await message.answer("❌ Дата должна быть в будущем. Попробуйте ещё раз:")
            return
        
        data = await state.get_data()
        task_id = data["editing_task_id"]
        
        async with AsyncSessionLocal() as session:
            task = await session.get(Task, task_id)
            if task:
                old_date = task.due_date.strftime("%d.%m.%Y")
                task.due_date = new_date
                await session.commit()
                await message.answer(
                    f"✅ Дедлайн задачи изменён с {old_date} на {new_date.strftime('%d.%m.%Y')}",
                    reply_markup=main_menu_keyboard
                )
            else:
                await message.answer("❌ Задача не найдена", reply_markup=main_menu_keyboard)
        
        await state.clear()
        await show_checklist(message)
        
    except Exception:
        await message.answer("❌ Неверный формат даты. Напишите: ДД.ММ.ГГГГ")

@router.callback_query(F.data.startswith("task_delete_confirm_"))
async def confirm_task_delete(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[3])
    await callback.message.edit_reply_markup(reply_markup=get_task_delete_confirm_keyboard(task_id))
    await callback.answer()

@router.callback_query(F.data.startswith("task_delete_"))
async def delete_task(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        task = await session.get(Task, task_id)
        if task:
            title = task.title
            await session.delete(task)
            await session.commit()
            await callback.answer(f"✅ Задача «{title}» удалена", show_alert=True)
            await show_checklist(callback.message)
        else:
            await callback.answer("Задача не найдена!", show_alert=True)

@router.callback_query(F.data == "task_add")
async def start_add_task(callback: CallbackQuery, state: FSMContext):
    couple = await get_couple_by_chat_id(callback.message.chat.id)
    
    if not couple:
        await callback.answer("Сначала зарегистрируйтесь!", show_alert=True)
        return
    
    await state.update_data(adding_task_couple_id=couple.id)
    await callback.message.edit_text(
        "➕ Введите название новой задачи:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="checklist_back")]
        ])
    )
    await state.set_state(TaskEditStates.waiting_for_new_task_title)
    await callback.answer()

@router.message(TaskEditStates.waiting_for_new_task_title)
async def process_new_task_title(message: Message, state: FSMContext):
    title = message.text.strip()
    
    if len(title) < 3:
        await message.answer("❌ Название должно быть от 3 символов. Попробуйте ещё раз:")
        return
    
    await state.update_data(new_task_title=title)
    await message.answer(
        f"📅 Введите дату дедлайна для «{title}» (ДД.ММ.ГГГГ):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="checklist_back")]
        ])
    )
    await state.set_state(TaskEditStates.waiting_for_new_task_date)

@router.message(TaskEditStates.waiting_for_new_task_date)
async def process_new_task_date(message: Message, state: FSMContext):
    try:
        date_text = message.text.strip()
        for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
            try:
                due_date = datetime.strptime(date_text, fmt).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError("Неверный формат")
        
        if due_date < datetime.now().date():
            await message.answer("❌ Дата должна быть в будущем. Попробуйте ещё раз:")
            return
        
        data = await state.get_data()
        couple_id = data["adding_task_couple_id"]
        title = data["new_task_title"]
        
        category = "организация"
        lower_title = title.lower()
        if any(word in lower_title for word in ["платье", "костюм", "наряд"]):
            category = "платье"
        elif any(word in lower_title for word in ["фото", "видео", "съёмка"]):
            category = "фото"
        elif any(word in lower_title for word in ["декор", "украшение", "цветы"]):
            category = "декор"
        elif any(word in lower_title for word in ["гость", "приглашен", "приглашение"]):
            category = "гости"
        elif any(word in lower_title for word in ["еда", "торт", "банкет", "ресторан"]):
            category = "еда"
        elif any(word in lower_title for word in ["локация", "площадка", "место"]):
            category = "локация"
        
        async with AsyncSessionLocal() as session:
            new_task = Task(
                couple_id=couple_id,
                title=title,
                category=category,
                due_date=due_date,
                days_before_wedding=None,
                is_completed=False
            )
            session.add(new_task)
            await session.commit()
        
        await message.answer(
            f"✅ Задача «{title}» добавлена!\nДедлайн: {due_date.strftime('%d.%m.%Y')}",
            reply_markup=main_menu_keyboard
        )
        await state.clear()
        await show_checklist(message)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}\nПопробуйте ещё раз:")

# === БЮДЖЕТ ===
@router.message(F.text == "💰 Бюджет")
async def show_budget(message: Message, state: FSMContext):
    couple = await get_couple_by_chat_id(message.chat.id)
    
    if not couple:
        await message.answer("Сначала зарегистрируйтесь через /start")
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Expense).where(Expense.couple_id == couple.id).order_by(Expense.date.desc())
        )
        expenses = result.scalars().all()
        
        total_spent = sum(e.amount for e in expenses)
        remaining = couple.budget_total - total_spent
        spent_percent = (total_spent / couple.budget_total * 100) if couple.budget_total > 0 else 0
        
        categories = {}
        for expense in expenses:
            cat = expense.category
            categories[cat] = categories.get(cat, 0) + expense.amount
        
        text = "💰 <b>Ваш бюджет</b>\n\n"
        text += f"Общий бюджет: {format_currency(couple.budget_total)} ₽\n"
        text += f"Потрачено: {format_currency(total_spent)} ₽\n"
        text += f"Остаток: {format_currency(remaining)} ₽\n\n"
        text += f"{create_progress_bar(spent_percent)}\n\n"
        
        if spent_percent >= 100:
            text += "⚠️ <b>Бюджет исчерпан!</b> Рассмотрите возможность увеличения бюджета или сокращения расходов.\n\n"
        elif spent_percent >= 90:
            text += "🚨 <b>Внимание!</b> Осталось менее 10% бюджета!\n\n"
        elif spent_percent >= 75:
            text += "🔔 <b>Напоминание:</b> Потрачено более 75% бюджета\n\n"
        
        if categories:
            text += "🏆 <b>Топ категорий:</b>\n"
            top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
            for i, (cat, amount) in enumerate(top_cats, 1):
                cat_percent = amount / couple.budget_total * 100
                text += f"{i}. {cat.capitalize()}: {format_currency(amount)} ₽ ({cat_percent:.0f}%)\n"
        else:
            text += "📭 Пока нет трат. Нажмите «➕ Добавить трату», чтобы начать!\n"
        
        await message.answer(
            text,
            reply_markup=get_budget_keyboard(),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "budget_refresh")
async def refresh_budget(callback: CallbackQuery):
    await callback.answer("🔄 Обновляю...")
    await show_budget(callback.message, FSMContext(storage=None, key=None))

@router.callback_query(F.data == "budget_back")
async def budget_back(callback: CallbackQuery):
    await callback.answer()
    await show_budget(callback.message, FSMContext(storage=None, key=None))

@router.callback_query(F.data == "budget_add_expense")
async def start_add_expense(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Добавление траты</b>\n\n"
        "Выберите категорию:",
        reply_markup=get_expense_category_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(BudgetStates.waiting_for_expense)
    await callback.answer()

@router.callback_query(F.data.startswith("expense_cat_"))
async def select_expense_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[2]
    await state.update_data(expense_category=category)
    
    await callback.message.edit_text(
        f"💰 Укажите сумму траты на <b>{category}</b> (в рублях):\n"
        f"Пример: 25000",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="budget_add_expense")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(BudgetStates.waiting_for_expense_description)
    await callback.answer()

@router.message(BudgetStates.waiting_for_expense_description)
async def process_expense_amount(message: Message, state: FSMContext):
    try:
        amount_text = re.sub(r"[^\d.]", "", message.text)
        amount = float(amount_text)
        
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной. Попробуйте ещё раз:")
            return
        
        data = await state.get_data()
        category = data["expense_category"]
        
        couple = await get_couple_by_chat_id(message.chat.id)
        
        if not couple:
            await message.answer("Ошибка: пара не найдена", reply_markup=main_menu_keyboard)
            await state.clear()
            return
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Expense).where(Expense.couple_id == couple.id)
            )
            expenses = result.scalars().all()
            total_spent = sum(e.amount for e in expenses)
            new_total = total_spent + amount
            
            if new_total > couple.budget_total * 1.1 and amount > couple.budget_total * 0.2:
                await state.update_data(expense_amount=amount)
                await message.answer(
                    f"⚠️ <b>Внимание!</b>\n\n"
                    f"Эта трата ({format_currency(amount)} ₽) превысит ваш бюджет на "
                    f"{format_currency(new_total - couple.budget_total)} ₽.\n\n"
                    f"Вы уверены, что хотите добавить эту трату?",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✅ Да, добавить", callback_data="expense_confirm_yes"),
                            InlineKeyboardButton(text="❌ Нет", callback_data="expense_confirm_no")
                        ]
                    ]),
                    parse_mode="HTML"
                )
                return
            
            expense = Expense(
                couple_id=couple.id,
                amount=amount,
                category=category,
                description=None,
                date=datetime.now().date()
            )
            session.add(expense)
            await session.commit()
        
        remaining = couple.budget_total - (total_spent + amount)
        await message.answer(
            f"✅ <b>Трата добавлена!</b>\n\n"
            f"Категория: {category.capitalize()}\n"
            f"Сумма: {format_currency(amount)} ₽\n"
            f"Остаток бюджета: {format_currency(remaining)} ₽",
            reply_markup=main_menu_keyboard,
            parse_mode="HTML"
        )
        await state.clear()
        await show_budget(message, FSMContext(storage=None, key=None))
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}\nПопробуйте ещё раз:")

@router.callback_query(F.data == "expense_confirm_yes")
async def confirm_expense(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data["expense_amount"]
    category = data["expense_category"]
    
    couple = await get_couple_by_chat_id(callback.message.chat.id)
    
    if couple:
        async with AsyncSessionLocal() as session:
            expense = Expense(
                couple_id=couple.id,
                amount=amount,
                category=category,
                description=None,
                date=datetime.now().date()
            )
            session.add(expense)
            await session.commit()
        
        await callback.message.edit_text(
            f"✅ <b>Трата добавлена!</b>\n\n"
            f"Категория: {category.capitalize()}\n"
            f"Сумма: {format_currency(amount)} ₽",
            parse_mode="HTML"
        )
        await state.clear()
        await callback.answer()

@router.callback_query(F.data == "expense_confirm_no")
async def cancel_expense(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Добавление траты отменено",
        reply_markup=main_menu_keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "budget_by_category")
async def show_budget_by_category(callback: CallbackQuery):
    couple = await get_couple_by_chat_id(callback.message.chat.id)
    
    if not couple:
        await callback.answer("Пара не найдена", show_alert=True)
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Expense).where(Expense.couple_id == couple.id)
        )
        expenses = result.scalars().all()
        
        categories = {}
        for expense in expenses:
            cat = expense.category
            categories[cat] = categories.get(cat, 0) + expense.amount
        
        text = "📊 <b>Бюджет по категориям</b>\n\n"
        total_spent = sum(categories.values())
        
        if not categories:
            text += "📭 Нет трат по категориям"
        else:
            all_categories = ["локация", "фото", "платье", "костюм", "декор", "еда", "гости", "музыка", "транспорт", "организация"]
            
            for cat in all_categories:
                spent = categories.get(cat, 0)
                if spent > 0 or cat in ["локация", "фото", "платье", "костюм"]:
                    percent = (spent / couple.budget_total * 100) if couple.budget_total > 0 else 0
                    bar = create_progress_bar(percent, 10)
                    text += f"{cat.capitalize():12} {format_currency(spent):>10} ₽ {bar}\n"
        
        text += f"\n{'─' * 30}\n"
        text += f"Итого потрачено: {format_currency(total_spent)} ₽"
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="budget_back")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

@router.callback_query(F.data == "budget_history")
async def show_budget_history(callback: CallbackQuery):
    couple = await get_couple_by_chat_id(callback.message.chat.id)
    
    if not couple:
        await callback.answer("Пара не найдена", show_alert=True)
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Expense)
            .where(Expense.couple_id == couple.id)
            .order_by(Expense.date.desc())
            .limit(10)
        )
        expenses = result.scalars().all()
        
        text = "📈 <b>История последних трат</b>\n\n"
        
        if not expenses:
            text += "📭 Нет записанных трат"
        else:
            for i, expense in enumerate(expenses, 1):
                date_str = expense.date.strftime("%d.%m")
                text += f"{i}. {date_str} | {expense.category.capitalize():10} | {format_currency(expense.amount):>10} ₽"
                if expense.description:
                    text += f"\n   └ {expense.description}"
                text += "\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="budget_back")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

@router.callback_query(F.data.startswith("quick_expense_"))
async def quick_add_expense(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    task_id = int(parts[2])
    category = parts[3]
    
    await state.update_data(expense_category=category, from_task_id=task_id)
    
    await callback.message.edit_text(
        f"💰 Быстрое добавление траты\nКатегория: <b>{category}</b>\n\n"
        f"Укажите сумму (в рублях):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"task_detail_{task_id}")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(BudgetStates.waiting_for_expense_description)
    await callback.answer()

# === ГОСТИ ===
@router.message(F.text == "👥 Гости")
async def show_guests(message: Message):
    couple = await get_couple_by_chat_id(message.chat.id)
    
    if not couple:
        await message.answer("Сначала зарегистрируйтесь через /start")
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Guest).where(Guest.couple_id == couple.id).order_by(Guest.name)
        )
        guests = result.scalars().all()
        
        total = len(guests)
        confirmed = sum(1 for g in guests if g.is_confirmed)
        declined = sum(1 for g in guests if g.will_not_come)
        pending = total - confirmed - declined
        
        text = "👥 <b>Управление гостями</b>\n\n"
        text += f"Всего гостей: {total}\n"
        text += f"✅ Подтвердили: {confirmed}\n"
        text += f"❌ Отказались: {declined}\n"
        text += f"⏳ Ждут ответа: {pending}\n\n"
        
        if total == 0:
            text += "📭 Пока нет гостей. Нажмите «➕ Добавить гостя», чтобы начать!"
        else:
            text += "Нажмите кнопки ниже для управления:"
        
        await message.answer(
            text,
            reply_markup=get_guests_keyboard(),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "guests_refresh")
async def refresh_guests(callback: CallbackQuery):
    await callback.answer("🔄 Обновляю...")
    await show_guests(callback.message)

@router.callback_query(F.data == "guests_back")
async def guests_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_guests(callback.message)
    await callback.answer()

@router.callback_query(F.data == "guests_add")
async def start_add_guest(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Добавление гостя</b>\n\n"
        "Введите имя гостя (и фамилию при желании):\n"
        "Пример: Иван Петров",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="guests_back")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(GuestStates.waiting_for_guest_name)
    await callback.answer()

@router.message(GuestStates.waiting_for_guest_name)
async def process_guest_name(message: Message, state: FSMContext):
    name = message.text.strip()
    
    if len(name) < 2:
        await message.answer("❌ Имя должно быть от 2 символов. Попробуйте ещё раз:")
        return
    
    await state.update_data(guest_name=name)
    await message.answer(
        f"📱 Укажите контактные данные для {name} (телефон или email):\n"
        "Можно пропустить — нажмите «➡️ Пропустить»",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Пропустить", callback_data="guest_skip_contact")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="guests_back")]
        ])
    )
    await state.set_state(GuestStates.waiting_for_guest_contact)

@router.callback_query(F.data == "guest_skip_contact")
async def skip_guest_contact(callback: CallbackQuery, state: FSMContext):
    await state.update_data(guest_phone=None, guest_email=None)
    await callback.message.edit_text(
        "✏️ Укажите пожелания или аллергии гостя (опционально):\n"
        "Пример: вегетарианец, аллергия на орехи",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Пропустить", callback_data="guest_skip_notes")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="guests_back")]
        ])
    )
    await state.set_state(GuestStates.waiting_for_guest_notes)
    await callback.answer()

@router.message(GuestStates.waiting_for_guest_contact)
async def process_guest_contact(message: Message, state: FSMContext):
    contact = message.text.strip()
    
    if "@" in contact and "." in contact:
        await state.update_data(guest_email=contact, guest_phone=None)
    else:
        phone = re.sub(r"[^\d+]", "", contact)
        if len(phone) < 10:
            await message.answer("❌ Неверный формат телефона. Попробуйте ещё раз или нажмите «➡️ Пропустить»:")
            return
        await state.update_data(guest_phone=phone, guest_email=None)
    
    await message.answer(
        "✏️ Укажите пожелания или аллергии гостя (опционально):\n"
        "Пример: вегетарианец, аллергия на орехи",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Пропустить", callback_data="guest_skip_notes")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="guests_back")]
        ])
    )
    await state.set_state(GuestStates.waiting_for_guest_notes)

@router.callback_query(F.data == "guest_skip_notes")
async def skip_guest_notes(callback: CallbackQuery, state: FSMContext):
    await state.update_data(guest_notes=None)
    await finish_add_guest(callback.message, state)
    await callback.answer()

@router.message(GuestStates.waiting_for_guest_notes)
async def process_guest_notes(message: Message, state: FSMContext):
    notes = message.text.strip() if message.text else None
    await state.update_data(guest_notes=notes)
    await finish_add_guest(message, state)

async def finish_add_guest(message_or_callback, state: FSMContext):
    data = await state.get_data()
    
    couple = await get_couple_by_chat_id(message_or_callback.chat.id)
    
    if not couple:
        if hasattr(message_or_callback, 'message'):
            await message_or_callback.message.answer("Ошибка: пара не найдена", reply_markup=main_menu_keyboard)
        else:
            await message_or_callback.answer("Ошибка: пара не найдена", reply_markup=main_menu_keyboard)
        await state.clear()
        return
    
    async with AsyncSessionLocal() as session:
        guest = Guest(
            couple_id=couple.id,
            name=data["guest_name"],
            phone=data.get("guest_phone"),
            email=data.get("guest_email"),
            dietary_notes=data.get("guest_notes"),
            is_confirmed=False,
            will_not_come=False,
            has_plus_one=False,
            created_at=datetime.now().date()
        )
        session.add(guest)
        await session.commit()
    
    response_text = f"✅ <b>Гость добавлен!</b>\n\nИмя: {data['guest_name']}"
    if data.get("guest_phone"):
        response_text += f"\nТелефон: {data['guest_phone']}"
    elif data.get("guest_email"):
        response_text += f"\nEmail: {data['guest_email']}"
    if data.get("guest_notes"):
        response_text += f"\nПожелания: {data['guest_notes']}"
    
    if hasattr(message_or_callback, 'message'):
        await message_or_callback.message.edit_text(
            response_text,
            reply_markup=main_menu_keyboard,
            parse_mode="HTML"
        )
    else:
        await message_or_callback.answer(
            response_text,
            reply_markup=main_menu_keyboard,
            parse_mode="HTML"
        )
    
    await state.clear()
    await show_guests(message_or_callback if hasattr(message_or_callback, 'chat') else message_or_callback.message)

@router.callback_query(F.data == "guests_list")
async def show_guests_list(callback: CallbackQuery):
    couple = await get_couple_by_chat_id(callback.message.chat.id)
    
    if not couple:
        await callback.answer("Пара не найдена", show_alert=True)
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Guest).where(Guest.couple_id == couple.id).order_by(Guest.name)
        )
        guests = result.scalars().all()
        
        if not guests:
            await callback.message.edit_text(
                "📭 Список гостей пуст",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить гостя", callback_data="guests_add")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="guests_back")]
                ])
            )
            return
        
        confirmed = [g for g in guests if g.is_confirmed]
        declined = [g for g in guests if g.will_not_come]
        pending = [g for g in guests if not g.is_confirmed and not g.will_not_come]
        
        text = "👥 <b>Список гостей</b>\n\n"
        
        if confirmed:
            text += "✅ <b>Подтвердили участие:</b>\n"
            for i, guest in enumerate(confirmed, 1):
                text += f"{i}. {guest.name}"
                if guest.has_plus_one:
                    text += f" (+1: {guest.plus_one_name or '—'})"
                if guest.dietary_notes:
                    text += f" • {guest.dietary_notes}"
                text += "\n"
            text += "\n"
        
        if pending:
            text += "⏳ <b>Ждут ответа:</b>\n"
            for i, guest in enumerate(pending, 1):
                text += f"{i}. {guest.name}"
                if guest.phone:
                    text += f" • 📱 {guest.phone}"
                elif guest.email:
                    text += f" • ✉️ {guest.email}"
                text += "\n"
            text += "\n"
        
        if declined:
            text += "❌ <b>Не придут:</b>\n"
            for i, guest in enumerate(declined, 1):
                text += f"{i}. {guest.name}\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить гостя", callback_data="guests_add")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="guests_back")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

@router.callback_query(F.data == "guests_stats")
async def show_guests_stats(callback: CallbackQuery):
    couple = await get_couple_by_chat_id(callback.message.chat.id)
    
    if not couple:
        await callback.answer("Пара не найдена", show_alert=True)
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Guest).where(Guest.couple_id == couple.id)
        )
        guests = result.scalars().all()
        
        total = len(guests)
        confirmed = sum(1 for g in guests if g.is_confirmed)
        declined = sum(1 for g in guests if g.will_not_come)
        pending = total - confirmed - declined
        with_plus_one = sum(1 for g in guests if g.is_confirmed and g.has_plus_one)
        total_with_plus_one = confirmed + with_plus_one
        
        text = "📊 <b>Статистика гостей</b>\n\n"
        text += f"Всего приглашено: {total}\n"
        text += f"✅ Подтвердили: {confirmed} ({confirmed/total*100:.0f}%)\n"
        text += f"   включая +1: {with_plus_one} гостей\n"
        text += f"   итого мест: {total_with_plus_one}\n"
        text += f"❌ Отказались: {declined} ({declined/total*100:.0f}%)\n"
        text += f"⏳ Ждут ответа: {pending} ({pending/total*100:.0f}%)\n\n"
        
        if total > 0:
            confirmed_bar = "█" * int(confirmed/total*15)
            declined_bar = "▒" * int(declined/total*15)
            pending_bar = "░" * (15 - len(confirmed_bar) - len(declined_bar))
            text += f"Прогресс подтверждений:\n"
            text += f"{confirmed_bar}{declined_bar}{pending_bar} {confirmed}/{total}\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="guests_back")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

@router.callback_query(F.data.startswith("guest_confirm_"))
async def confirm_guest(callback: CallbackQuery):
    guest_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        guest = await session.get(Guest, guest_id)
        if not guest:
            await callback.answer("Гость не найден!", show_alert=True)
            return
        
        guest.is_confirmed = True
        guest.will_not_come = False
        await session.commit()
    
    await callback.answer(f"✅ {guest.name} подтвердил участие!", show_alert=True)
    await show_guests_list(callback)

@router.callback_query(F.data.startswith("guest_decline_"))
async def decline_guest(callback: CallbackQuery):
    guest_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        guest = await session.get(Guest, guest_id)
        if not guest:
            await callback.answer("Гость не найден!", show_alert=True)
            return
        
        guest.is_confirmed = False
        guest.will_not_come = True
        await session.commit()
    
    await callback.answer(f"❌ {guest.name} не придёт", show_alert=True)
    await show_guests_list(callback)

@router.callback_query(F.data.startswith("guest_unconfirm_"))
async def unconfirm_guest(callback: CallbackQuery):
    guest_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        guest = await session.get(Guest, guest_id)
        if not guest:
            await callback.answer("Гость не найден!", show_alert=True)
            return
        
        guest.is_confirmed = False
        guest.will_not_come = False
        await session.commit()
    
    await callback.answer(f"↩️ Статус {guest.name} сброшен", show_alert=True)
    await show_guests_list(callback)

@router.callback_query(F.data.startswith("guest_add_plus_one_"))
async def add_plus_one(callback: CallbackQuery, state: FSMContext):
    guest_id = int(callback.data.split("_")[4])
    
    async with AsyncSessionLocal() as session:
        guest = await session.get(Guest, guest_id)
        if not guest:
            await callback.answer("Гость не найден!", show_alert=True)
            return
    
    await state.update_data(editing_guest_id=guest_id)
    await callback.message.edit_text(
        f"➕ <b>+1 для {guest.name}</b>\n\n"
        f"Введите имя спутника/спутницы:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"guest_detail_{guest_id}")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(GuestStates.waiting_for_plus_one_name)
    await callback.answer()

@router.message(GuestStates.waiting_for_plus_one_name)
async def process_plus_one_name(message: Message, state: FSMContext):
    plus_one_name = message.text.strip()
    
    if len(plus_one_name) < 2:
        await message.answer("❌ Имя должно быть от 2 символов. Попробуйте ещё раз:")
        return
    
    data = await state.get_data()
    guest_id = data["editing_guest_id"]
    
    async with AsyncSessionLocal() as session:
        guest = await session.get(Guest, guest_id)
        if guest:
            guest.has_plus_one = True
            guest.plus_one_name = plus_one_name
            await session.commit()
            await message.answer(
                f"✅ +1 добавлен для {guest.name}!\nИмя спутника: {plus_one_name}",
                reply_markup=main_menu_keyboard
            )
        else:
            await message.answer("❌ Гость не найден", reply_markup=main_menu_keyboard)
    
    await state.clear()
    await show_guests(message)

@router.callback_query(F.data == "guests_invite_all")
async def guests_invite_all(callback: CallbackQuery):
    """Умная рассылка приглашений гостям с кнопками отправки"""
    couple = await get_couple_by_chat_id(callback.message.chat.id)
    
    if not couple:
        await callback.answer("Пара не найдена", show_alert=True)
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Guest).where(Guest.couple_id == couple.id).order_by(Guest.name)
        )
        guests = result.scalars().all()
        
        if not guests:
            await callback.message.edit_text(
                "📭 Нет гостей для приглашения.\n"
                "Сначала добавьте гостей через «➕ Добавить гостя».",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить гостя", callback_data="guests_add")],
                    [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="guests_list")]
                ])
            )
            await callback.answer()
            return
        
        # Формируем список гостей для приглашения
        text = "✉️ <b>Отправить приглашения гостям</b>\n\n"
        text += f"Найдено гостей: {len(guests)}\n\n"
        text += "Нажмите на гостя, чтобы подготовить персонализированное приглашение:\n\n"
        
        buttons = []
        for guest in guests:
            status_icon = "✅" if guest.is_confirmed else ("❌" if guest.will_not_come else "⏳")
            guest_text = f"{status_icon} {guest.name}"
            if guest.phone or guest.email:
                guest_text += " • 📱"
            buttons.append([
                InlineKeyboardButton(
                    text=guest_text,
                    callback_data=f"guest_invite_prepare_{guest.id}"
                )
            ])
        
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="guests_list")
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
        await callback.answer("✅ Список гостей для приглашения")

@router.callback_query(F.data.startswith("guest_invite_prepare_"))
async def prepare_guest_invite(callback: CallbackQuery):
    """Подготовить персонализированное приглашение для гостя"""
    guest_id = int(callback.data.split("_")[3])
    
    async with AsyncSessionLocal() as session:
        guest = await session.get(Guest, guest_id)
        if not guest:
            await callback.answer("Гость не найден", show_alert=True)
            return
        
        couple = await get_couple_by_chat_id(callback.message.chat.id)
        if not couple:
            await callback.answer("Пара не найдена", show_alert=True)
            return
        
        # Формируем персонализированную ссылку для гостя
        bot_username = (await callback.bot.get_me()).username
        invite_link = f"https://t.me/{bot_username}?start=guest_{guest.id}"
        
        # Показываем сообщение с кнопкой отправки (без лишнего текста в инлайн-запросе)
        await callback.message.edit_text(
            f"💌 <b>Приглашение для {guest.name}</b>\n\n"
            f"Нажмите кнопку ниже, чтобы отправить приглашение напрямую в чат гостя:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"📤 Отправить {guest.name}",
                        switch_inline_query=f"guest_{guest.id}"  # ← КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: только ID гостя
                    )
                ],
                [
                    InlineKeyboardButton(text="🔄 Другой гость", callback_data="guests_invite_all"),
                    InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="guests_list")
                ]
            ]),
            parse_mode="HTML"
        )
        await callback.answer(f"✅ Приглашение для {guest.name} готово к отправке")

@router.callback_query(F.data == "guests_list_from_task")
async def guests_list_from_task(callback: CallbackQuery):
    await show_guests_list(callback)

# === КНИГА ВОСПОМИНАНИЙ ===
@router.message(F.text == "📖 Книга воспоминаний")
async def show_memories(message: Message):
    couple = await get_couple_by_chat_id(message.chat.id)
    
    if not couple:
        await message.answer("Сначала зарегистрируйтесь через /start")
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Memory)
            .where(Memory.couple_id == couple.id)
            .where(Memory.answer != "")
            .order_by(Memory.asked_at.desc())
            .limit(5)
        )
        memories = result.scalars().all()
        
        text = "📖 <b>Ваша Книга воспоминаний</b>\n\n"
        
        if not memories:
            text += "📭 Пока пусто. Бот будет задавать вам вопросы каждую пятницу в 18:00.\n"
            text += "Ваши ответы сохранятся и будут отправлены вам в день свадьбы как подарок 💍"
        else:
            text += f"Сохранено записей: {len(memories)}\n\n"
            for i, memory in enumerate(memories[:5], 1):
                date_str = memory.asked_at.strftime("%d.%m")
                text += f"<b>{date_str}</b>\n"
                text += f"❓ {memory.question}\n"
                text += f"💬 {memory.answer[:100]}{'...' if len(memory.answer) > 100 else ''}\n\n"
            text += "━" * 30 + "\n"
            text += "\n<i>Полная книга будет отправлена вам в день свадьбы</i>"
        
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="memories_refresh")]
            ]),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("memory_answer_"))
async def start_memory_answer(callback: CallbackQuery, state: FSMContext):
    memory_id = int(callback.data.split("_")[2])
    
    await state.update_data(memory_id=memory_id)
    await callback.message.edit_text(
        "✏️ <b>Ваш ответ:</b>\n\nНапишите свой ответ одним сообщением:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="guests_back")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(MemoryStates.waiting_for_answer)
    await callback.answer()

@router.message(MemoryStates.waiting_for_answer)
async def process_memory_answer(message: Message, state: FSMContext):
    answer = message.text.strip()
    
    if len(answer) < 5:
        await message.answer("❌ Ответ должен быть от 5 символов. Попробуйте ещё раз:")
        return
    
    data = await state.get_data()
    memory_id = data["memory_id"]
    
    async with AsyncSessionLocal() as session:
        memory = await session.get(Memory, memory_id)
        if memory and memory.answer == "":
            memory.answer = answer
            memory.answered_at = datetime.now().date()
            await session.commit()
            
            await message.answer(
                "✅ <b>Ответ сохранён!</b>\n\n"
                "Ваша Книга воспоминаний пополнилась новой страницей 📖\n"
                "В день свадьбы вы получите полную книгу как подарок от меня 💍",
                reply_markup=main_menu_keyboard,
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "⚠️ Этот вопрос уже был отвечен ранее.",
                reply_markup=main_menu_keyboard
            )
    
    await state.clear()

# === НАСТРОЙКИ ===
@router.message(F.text == "⚙️ Настройки")
async def show_settings(message: Message):
    couple = await get_couple_by_chat_id(message.chat.id)
    
    if not couple:
        await message.answer("Сначала зарегистрируйтесь через /start")
        return
    
    days_left = (couple.wedding_date - datetime.now().date()).days
    
    text = "⚙️ <b>Настройки свадьбы</b>\n\n"
    text += f"👰 Имена: {couple.partner1_name} и {couple.partner2_name}\n"
    text += f"📅 Дата свадьбы: {couple.wedding_date.strftime('%d.%m.%Y')}\n"
    text += f"⏳ До свадьбы: {days_left} дней\n"
    text += f"💫 Стиль: {couple.wedding_type}\n"
    text += f"💰 Бюджет: {format_currency(couple.budget_total)} ₽\n\n"
    text += "Нажмите кнопку ниже, чтобы изменить любые данные:"
    
    # Клавиатура с кнопками редактирования + приглашение партнёра
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Изменить имена", callback_data="settings_edit_names"),
            InlineKeyboardButton(text="📅 Изменить дату", callback_data="settings_edit_date")
        ],
        [
            InlineKeyboardButton(text="💰 Изменить бюджет", callback_data="settings_edit_budget"),
            InlineKeyboardButton(text="🎭 Изменить стиль", callback_data="settings_edit_type")
        ],
        [
            InlineKeyboardButton(text="👥 Пригласить партнёра", callback_data="settings_invite_partner")
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="settings_refresh")
        ]
    ])
    
    await message.answer(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "settings_refresh")
async def refresh_settings(callback: CallbackQuery):
    await callback.answer("🔄 Обновляю...")
    await show_settings(callback.message)

# === ОБРАБОТЧИКИ РЕДАКТИРОВАНИЯ ===
@router.callback_query(F.data == "settings_edit_names")
async def start_edit_names(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ <b>Изменение имён</b>\n\n"
        "Напишите новые имена через 'и':\n"
        "Пример: Мария и Дмитрий",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="settings_back")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_partner_names_edit)
    await callback.answer()

@router.callback_query(F.data == "settings_edit_date")
async def start_edit_date(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📅 <b>Изменение даты свадьбы</b>\n\n"
        "Введите новую дату в формате ДД.ММ.ГГГГ:\n"
        "Пример: 15.09.2026",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="settings_back")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_wedding_date_edit)
    await callback.answer()

@router.callback_query(F.data == "settings_edit_budget")
async def start_edit_budget(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💰 <b>Изменение бюджета</b>\n\n"
        "Введите новый бюджет в рублях:\n"
        "Пример: 750000",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="settings_back")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_budget_edit)
    await callback.answer()

@router.callback_query(F.data == "settings_edit_type")
async def start_edit_type(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🎭 <b>Изменение стиля свадьбы</b>\n\n"
        "Выберите новый стиль:",
        reply_markup=get_wedding_type_inline_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_wedding_type_edit)
    await callback.answer()

@router.callback_query(F.data == "settings_back")
async def settings_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_settings(callback.message)
    await callback.answer()

# === ОБРАБОТЧИКИ ВВОДА НОВЫХ ДАННЫХ ===
@router.message(SettingsStates.waiting_for_partner_names_edit)
async def process_new_names(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    
    if " и " not in text:
        await message.answer("❌ Напишите два имени через 'и' (пример: Иван и Мария)")
        return
    
    names = [n.strip().capitalize() for n in text.split(" и ")]
    if len(names) != 2:
        await message.answer("❌ Напишите ровно два имени через 'и'")
        return
    
    partner1, partner2 = names
    
    couple = await get_couple_by_chat_id(message.chat.id)
    
    if couple:
        old_names = f"{couple.partner1_name} и {couple.partner2_name}"
        couple.partner1_name = partner1
        couple.partner2_name = partner2
        
        async with AsyncSessionLocal() as session:
            await session.commit()
        
        await message.answer(
            f"✅ Имена изменены!\n"
            f"Было: {old_names}\n"
            f"Стало: {partner1} и {partner2}",
            reply_markup=main_menu_keyboard
        )
    else:
        await message.answer("❌ Ошибка: пара не найдена", reply_markup=main_menu_keyboard)
    
    await state.clear()
    await show_settings(message)

@router.message(SettingsStates.waiting_for_wedding_date_edit)
async def process_new_date_edit(message: Message, state: FSMContext):
    try:
        date_text = message.text.strip()
        for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
            try:
                new_date = datetime.strptime(date_text, fmt).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError("Неверный формат")
        
        if new_date <= datetime.now().date():
            await message.answer("❌ Дата свадьбы должна быть в будущем. Попробуйте ещё раз:")
            return
        
        couple = await get_couple_by_chat_id(message.chat.id)
        
        if couple:
            old_date = couple.wedding_date.strftime('%d.%m.%Y')
            old_days_left = (couple.wedding_date - datetime.now().date()).days
            
            # Обновляем дату свадьбы
            couple.wedding_date = new_date
            
            async with AsyncSessionLocal() as session:
                await session.commit()
                
                # Пересчитываем дедлайны задач
                result = await session.execute(
                    select(Task).where(Task.couple_id == couple.id)
                )
                tasks = result.scalars().all()
                
                days_diff = (new_date - datetime.strptime(old_date, '%d.%m.%Y').date()).days
                updated_tasks = 0
                
                for task in tasks:
                    if task.due_date:
                        task.due_date = task.due_date + timedelta(days=days_diff)
                        updated_tasks += 1
                
                await session.commit()
            
            new_days_left = (new_date - datetime.now().date()).days
            await message.answer(
                f"✅ Дата свадьбы изменена!\n"
                f"Было: {old_date} ({old_days_left} дней до свадьбы)\n"
                f"Стало: {new_date.strftime('%d.%m.%Y')} ({new_days_left} дней до свадьбы)\n\n"
                f"🔄 Дедлайны {updated_tasks} задач автоматически пересчитаны!",
                reply_markup=main_menu_keyboard
            )
        else:
            await message.answer("❌ Ошибка: пара не найдена", reply_markup=main_menu_keyboard)
        
        await state.clear()
        await show_settings(message)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}\nПопробуйте ещё раз:")

@router.message(SettingsStates.waiting_for_budget_edit)
async def process_new_budget_edit(message: Message, state: FSMContext):
    try:
        budget_text = re.sub(r"[^\d.]", "", message.text)
        budget = float(budget_text)
        
        if budget <= 0:
            await message.answer("❌ Бюджет должен быть положительным. Попробуйте ещё раз:")
            return
        
        if budget < 10000:
            await message.answer("❌ Такой бюджет маловат для свадьбы 😅 Укажите реальную сумму:")
            return
        
        couple = await get_couple_by_chat_id(message.chat.id)
        
        if couple:
            old_budget = couple.budget_total
            couple.budget_total = budget
            
            async with AsyncSessionLocal() as session:
                await session.commit()
                
                # Пересчитываем прогресс бюджета
                result = await session.execute(
                    select(Expense).where(Expense.couple_id == couple.id)
                )
                expenses = result.scalars().all()
                total_spent = sum(e.amount for e in expenses)
                spent_percent = (total_spent / budget * 100) if budget > 0 else 0
            
            await message.answer(
                f"✅ Бюджет изменён!\n"
                f"Было: {format_currency(old_budget)} ₽\n"
                f"Стало: {format_currency(budget)} ₽\n\n"
                f"📊 Текущий прогресс: {spent_percent:.0f}% потрачено",
                reply_markup=main_menu_keyboard
            )
        else:
            await message.answer("❌ Ошибка: пара не найдена", reply_markup=main_menu_keyboard)
        
        await state.clear()
        await show_settings(message)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}\nПопробуйте ещё раз:")

# === КЛЮЧЕВОЙ ОБРАБОТЧИК: ВЫБОР СТИЛЯ ЧЕРЕЗ ИНЛАЙН-КНОПКИ ===
@router.callback_query(
    SettingsStates.waiting_for_wedding_type_edit,
    F.data.startswith("wedding_type_edit_")
)
async def process_wedding_type_edit(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора стиля через инлайн-кнопки при редактировании"""
    # Извлекаем стиль из коллбэк-данных (после префикса "wedding_type_edit_")
    wedding_type = callback.data.split("_", 3)[3]
    
    couple = await get_couple_by_chat_id(callback.message.chat.id)
    
    if couple:
        old_type = couple.wedding_type
        couple.wedding_type = wedding_type
        
        async with AsyncSessionLocal() as session:
            await session.commit()
        
        # Подтверждаем изменение
        await callback.message.edit_text(
            f"✅ Стиль свадьбы изменён!\n"
            f"Было: {old_type}\n"
            f"Стало: {wedding_type}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Вернуться в настройки", callback_data="settings_back")]
            ])
        )
    else:
        await callback.answer("❌ Ошибка: пара не найдена", show_alert=True)
    
    await state.clear()
    await callback.answer()

# === ЭКСПОРТ В PDF ===
@router.callback_query(F.data == "export_pdf")
async def export_to_pdf(callback: CallbackQuery):
    """Генерация и отправка PDF-отчёта с защитой от всех ошибок"""
    try:
        couple = await get_couple_by_chat_id(callback.message.chat.id)
        
        if not couple:
            await callback.answer("Сначала зарегистрируйтесь через /start", show_alert=True)
            return
        
        async with AsyncSessionLocal() as session:
            # Получаем задачи
            result = await session.execute(
                select(Task).where(Task.couple_id == couple.id).order_by(Task.due_date)
            )
            tasks = result.scalars().all()
            
            # Получаем траты
            result = await session.execute(
                select(Expense).where(Expense.couple_id == couple.id).order_by(Expense.date.desc())
            )
            expenses = result.scalars().all()
            
            # Получаем гостей
            result = await session.execute(
                select(Guest).where(Guest.couple_id == couple.id).order_by(Guest.name)
            )
            guests = result.scalars().all()
        
        # Формируем данные для отчёта
        couple_data = {
            "partner1_name": couple.partner1_name,
            "partner2_name": couple.partner2_name,
            "wedding_date": couple.wedding_date,
            "days_left": (couple.wedding_date - datetime.now().date()).days,
            "wedding_type": couple.wedding_type,
            "budget_total": couple.budget_total
        }
        
        # Генерируем PDF в памяти
        from pdf_generator import generate_wedding_report
        pdf_buffer = generate_wedding_report(couple_data, tasks, expenses, guests)
        
        # ПОДГОТАВЛИВАЕМ ФАЙЛ ДЛЯ ОТПРАВКИ
        pdf_buffer.seek(0)
        pdf_content = pdf_buffer.read()
        pdf_buffer.close()
        
        # Создаём правильный объект файла для Telegram
        pdf_file = BufferedInputFile(
            file=pdf_content,
            filename=f"svadba_{couple.wedding_date.strftime('%Y%m%d')}.pdf"
        )
        
        # Отправляем файл с КОРОТКОЙ подписью
        await callback.message.answer_document(
            document=pdf_file,
            caption=f"📄 Свадьба {couple.wedding_date.strftime('%d.%m.%Y')}\n"
                   f"{couple.partner1_name} & {couple.partner2_name}",
            parse_mode="HTML"
        )
        
        # Отправляем подтверждающее сообщение ОТДЕЛЬНО
        await callback.message.answer(
            "✅ Отчёт успешно сформирован!\n\n"
            "📄 В файле:\n"
            "• Чек-лист задач с дедлайнами\n"
            "• Детализация бюджета по категориям\n"
            "• Список гостей с подтверждениями\n"
            "• Статистика подготовки\n\n"
            "💡 Совет: распечатайте для встречи с родителями или организатором!",
            reply_markup=main_menu_keyboard
        )
        
        await callback.answer("✅ PDF отправлен!")
    
    except Exception as e:
        error_msg = str(e)[:150]
        await callback.answer(f"❌ Ошибка: {error_msg}", show_alert=True)
        logger.error(f"Ошибка генерации PDF для {callback.message.chat.id}: {e}")

# === СОВМЕСТНЫЙ ДОСТУП ДЛЯ ПАРТНЁРОВ ===
def generate_share_token():
    """Генерация уникального 12-символьного токена для приглашения"""
    return secrets.token_urlsafe(9)[:12]

@router.callback_query(F.data == "settings_invite_partner")
async def invite_partner(callback: CallbackQuery):
    """Генерация ссылки-приглашения для партнёра с кнопкой отправки"""
    async with AsyncSessionLocal() as session:
        # Получаем пару НАПРЯМУЮ в текущей сессии (без вызова внешней функции!)
        result = await session.execute(
            select(Couple).where(
                (Couple.chat_id == callback.message.chat.id) | 
                (Couple.partner_chat_id == callback.message.chat.id)
            )
        )
        couple = result.scalar_one_or_none()
        
        if not couple:
            await callback.answer("Ошибка: пара не найдена", show_alert=True)
            return
        
        # Проверяем, есть ли уже второй партнёр
        if couple.partner_chat_id and couple.partner_chat_id != callback.message.chat.id:
            await callback.message.edit_text(
                "👥 <b>Совместный доступ</b>\n\n"
                f"✅ Ваш партнёр уже привязан к этой свадьбе!\n\n"
                f"Оба партнёра могут управлять подготовкой в реальном времени.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад в настройки", callback_data="settings_back")]
                ]),
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        # Генерируем токен, если его нет И СРАЗУ СОХРАНЯЕМ В БД
        if not couple.share_token:
            couple.share_token = generate_share_token()
            await session.commit()  # ← Сохраняем в ТОЙ ЖЕ сессии!
            logger.info(f"🔑 Сгенерирован и сохранён токен {couple.share_token} для пары {couple.id}")
        else:
            logger.info(f"🔑 Используется существующий токен {couple.share_token} для пары {couple.id}")
        
        # Формируем ЧИСТУЮ ссылку
        bot_username = (await callback.bot.get_me()).username
        invite_link = f"https://t.me/{bot_username}?start=share_{couple.share_token}"
        logger.info(f"📤 Ссылка для приглашения: {invite_link}")
        
        # Отправляем сообщение с кнопкой отправки
        await callback.message.edit_text(
            "👥 <b>Пригласить партнёра</b>\n\n"
            "Нажмите кнопку ниже, чтобы отправить приглашение напрямую в чат партнёра:\n\n"
            "📤 <b>Как это работает:</b>\n"
            "1. Нажмите «📤 Пригласить партнёра»\n"
            "2. Выберите чат с вашим партнёром из списка\n"
            "3. Партнёр получит сообщение с ссылкой\n"
            "4. После перехода по ссылке он автоматически присоединится к вашей свадьбе",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📤 Пригласить партнёра",
                        switch_inline_query=f"Присоединяйся к нашей свадьбе! {invite_link}"
                    )
                ],
                [
                    InlineKeyboardButton(text="🔄 Обновить ссылку", callback_data="settings_regenerate_link"),
                    InlineKeyboardButton(text="⬅️ Назад в настройки", callback_data="settings_back")
                ]
            ]),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        await callback.answer("✅ Ссылка готова к отправке")

@router.callback_query(F.data == "settings_regenerate_link")
async def regenerate_invite_link(callback: CallbackQuery):
    """Перегенерация ссылки-приглашения"""
    couple = await get_couple_by_chat_id(callback.message.chat.id)
    
    if couple:
        couple.share_token = generate_share_token()
        
        async with AsyncSessionLocal() as session:
            await session.commit()
        
        await invite_partner(callback)
    else:
        await callback.answer("Ошибка: пара не найдена", show_alert=True)
        from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent
import uuid

# === ИНЛАЙН-ЗАПРОСЫ ДЛЯ ОТПРАВКИ ПРИГЛАШЕНИЙ ===
@router.inline_query()
async def handle_inline_invite(inline_query: InlineQuery):
    """Обработка инлайн-запросов для отправки приглашений (партнёра и гостей)"""
    query = inline_query.query.strip()
    
    # === ОБРАБОТКА ПРИГЛАШЕНИЯ ПАРТНЁРА ===
    if query.startswith("Присоединяйся к нашей свадьбе!"):
        # Извлекаем ссылку из запроса
        invite_link = query.replace("Присоединяйся к нашей свадьбе! ", "").strip()
        
        result = InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="👰🤵 Пригласить на свадьбу",
            input_message_content=InputTextMessageContent(
                message_text=(
                    "💍 <b>Вас приглашают на свадьбу!</b>\n\n"
                    "Ваш партнёр хочет, чтобы вы присоединились к подготовке к свадьбе.\n"
                    "Нажмите на ссылку ниже, чтобы получить доступ ко всем задачам, бюджету и списку гостей:\n\n"
                    f"{invite_link}"
                ),
                parse_mode="HTML",
                disable_web_page_preview=True
            ),
            description="Нажмите, чтобы отправить приглашение",
            thumb_url="https://cdn-icons-png.flaticon.com/512/25/25694.png"
        )
        
        await inline_query.answer(
            results=[result],
            cache_time=1,
            switch_pm_text="Подтвердите участие в свадьбе",
            switch_pm_parameter="start"
        )
        return
    
    # === ОБРАБОТКА ПРИГЛАШЕНИЯ ГОСТЯ ===
    if query.startswith("guest_"):
        try:
            guest_id = int(query.split("_", 1)[1])
        except (IndexError, ValueError):
            await inline_query.answer(
                results=[],
                cache_time=1,
                switch_pm_text="Неверный формат приглашения",
                switch_pm_parameter="start"
            )
            return
        
        # Получаем данные из БД
        async with AsyncSessionLocal() as session:
            guest = await session.get(Guest, guest_id)
            if not guest:
                await inline_query.answer(
                    results=[],
                    cache_time=1,
                    switch_pm_text="Гость не найден",
                    switch_pm_parameter="start"
                )
                return
            
            couple = await session.get(Couple, guest.couple_id)
            if not couple:
                await inline_query.answer(
                    results=[],
                    cache_time=1,
                    switch_pm_text="Свадьба не найдена",
                    switch_pm_parameter="start"
                )
                return
            
            # Формируем КРАСИВОЕ сообщение с переносами строк \n
            bot_username = (await inline_query.bot.get_me()).username
            invite_link = f"https://t.me/{bot_username}?start=guest_{guest.id}"
            
            message_text = (
                f"Приглашение на свадьбу!\n\n"
                f"Дорогой(ая) {guest.name}!\n\n"
                f"Мы с радостью приглашаем тебя на нашу свадьбу:\n"
                f"👰🤵 {couple.partner1_name} и {couple.partner2_name}\n"
                f"📅 {couple.wedding_date.strftime('%d.%m.%Y')}\n\n"
                f"Пожалуйста, подтверди своё участие до {couple.wedding_date.strftime('%d.%m.%Y')}:\n"
                f"👉 {invite_link}\n\n"
                f"С любовью, {couple.partner1_name} и {couple.partner2_name} 💍"
            )
            
            result = InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=f"💌 Пригласить {guest.name}",
                input_message_content=InputTextMessageContent(
                    message_text=message_text,
                    parse_mode="HTML",  # ← HTML для красивого форматирования
                    disable_web_page_preview=True
                ),
                description="Нажмите, чтобы отправить приглашение",
                thumb_url="https://cdn-icons-png.flaticon.com/512/25/25694.png",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Подтвердить участие", url=invite_link)]
                ])
            )
            
            await inline_query.answer(
                results=[result],
                cache_time=1,
                switch_pm_text="Подтвердите участие в свадьбе",
                switch_pm_parameter="start"
            )
            return
    
    # Если запрос не распознан — не показываем результатов
    await inline_query.answer(
        results=[],
        cache_time=1,
        switch_pm_text="Сначала добавьте гостей в боте",
        switch_pm_parameter="start"
    )