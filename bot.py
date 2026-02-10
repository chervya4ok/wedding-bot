import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from config import BOT_TOKEN
from database.db import init_db, AsyncSessionLocal
from database.models import Task, Couple, Memory
from sqlalchemy import select
from datetime import datetime, timedelta
import random

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Глобальный планировщик
scheduler = AsyncIOScheduler()

# === ЕЖЕДНЕВНЫЕ МОТИВАЦИОННЫЕ СООБЩЕНИЯ С ПЕРСОНАЛИЗАЦИЕЙ ===
DAILY_MESSAGES_EARLY = [
    "Самое время мечтать! Напишите список из 5 вещей, которые вы хотите видеть на своей свадьбе — даже самых необычных ✨",
    "Факт: в среднем пара тратит 217 часов на подготовку. Вы только начинаете — и это прекрасно! Время на вашей стороне 💫",
    "Совет дня: создайте общую папку в облаке для вдохновения (скриншоты локаций, образов, декора). Это сэкономит часы споров позже!",
    "Знаете ли вы? В Дании жених должен вырезать сердце из дерева и подарить невесте — символ готовности строить дом вместе ❤️",
    "Не спешите с выбором. Лучшие решения приходят, когда вы не торопитесь. Выделите сегодня 10 минут просто помечтать вместе 🌸",
    "В Японии перед свадьбой пара сажает дерево сакуры — символ роста любви. Какой символ вы бы выбрали для своей истории? 🌸",
    "Совет дня: сфотографируйте закат сегодня вместе. Это напомнит, ради чего вы проходите всю эту подготовку 🌅",
    "Факт: белое платье стало традицией только после свадьбы королевы Виктории в 1840 году. Ваша свадьба — ваши правила! 👑",
]

DAILY_MESSAGES_MID = [
    "Вы уже сделали 40% подготовки! Гордитесь собой — многие пары на этом этапе чувствуют усталость, но вы справляетесь 💪",
    "Совет дня: выделите 15 минут сегодня, чтобы просто обнять друг друга без разговоров о свадьбе ❤️",
    "Факт: в Грузии на свадьбе принято разбивать тарелку — чем громче звук, тем крепче будет брак 🍽️",
    "В Индии свадьбы длятся до 7 дней — но главный секрет счастья там прост: 'Не сравнивайте свою свадьбу с чужой'",
    "Совет дня: сфотографируйте образцы тканей для декора — так проще согласовать цвета с флористом",
    "Вы сегодня уже 2 часа занимались подготовкой. Сделайте перерыв на чай с любимым человеком ☕️",
    "Факт: в Швеции жених и невеста дарят друг другу по 3 подарка: символизируя прошлое, настоящее и будущее",
    "Напоминание: идеальной свадьбы не бывает. Но ваша свадьба будет идеальной для вас двоих — и этого достаточно 💫",
    "В Бразилии невеста носит на запястье зелёную ленту — символ удачи и процветания 🌿",
    "Самый частый совет от пар, уже прошедших свадьбу: 'Не пытайтесь контролировать всё. Доверьтесь профессионалам'",
]

DAILY_MESSAGES_LATE = [
    "Осталось меньше двух месяцев! Вы прошли долгий путь — теперь самое время наслаждаться каждым днём подготовки ✨",
    "Совет дня: запишите 3 вещи, за которые вы благодарны друг другу сегодня. Это напомнит, ради чего вся эта подготовка 💕",
    "Факт: самая длинная свадьба в истории длилась 91 год — пара просто ежегодно отмечала годовщину как 'продление клятв'",
    "Вы не 'тратите время' на подготовку к свадьбе. Вы инвестируете в воспоминания, которые будут греть вас 50 лет",
    "В Италии жених дарит невесте 'ла бомба' — коробку с конфетами, символизирующую сладость брака 🍬",
    "Напоминание: если сегодня был сложный день — это нормально. Завтра будет легче. А свадьба всё равно состоится и будет прекрасной",
    "Самый красивый момент свадьбы, по опросу 10 000 пар: не первый танец и не клятвы, а момент, когда вы впервые увидели друг друга в этот день 👀",
    "Сегодня вы на 1% ближе к самому важному дню в вашей жизни! 💍",
]

DAILY_MESSAGES_FINAL = [
    "Завтра большой день! Вы прошли этот путь вместе — и это самое важное. Отдохните сегодня и насладитесь моментом 💫",
    "Совет дня: лягте спать пораньше. Завтра вы будете сиять от усталости и счастья — но сон сделает это сияние мягким ✨",
    "Помните: даже если что-то пойдёт не по плану — это станет вашей уникальной историей. А история любви важнее идеального сценария ❤️",
    "Вы уже победители. Потому что нашли друг друга. Всё остальное — просто красивое оформление вашей любви 💍",
    "С днём перед свадьбой! Сегодня разрешается волноваться, но помните: вы идеальная пара именно такой, какая вы есть 🌸",
]

DAILY_MESSAGES_WEDDING_DAY = [
    "🎉 С ДНЁМ СВАДЬБЫ! 💍✨\n\nПусть этот день будет наполнен любовью, смехом и моментами, которые вы будете вспоминать с улыбкой через 50 лет ❤️",
    "👰🤵 СЕГОДНЯ ВАШ ДЕНЬ!\n\nВы прошли долгий путь подготовки. Теперь просто будьте здесь и сейчас — друг с другом, в любви и радости ✨",
    "💫 С ДНЁМ СВАДЬБЫ!\n\nПусть даже мелкие неприятности (пролитое шампанское, задержка машины) станут смешными историями, которые вы будете рассказывать внукам 😊",
]

# === ВОПРОСЫ ДЛЯ КНИГИ ВОСПОМИНАНИЙ ===
MEMORY_QUESTIONS_EARLY = [
    "💭 Что вас больше всего волнует в подготовке к свадьбе?",
    "💭 Какой момент сегодня заставил вас улыбнуться при мысли о свадьбе?",
    "💭 Если бы свадьба была песней — какую вы бы выбрали и почему?",
    "💭 Что вы хотите запомнить из этого этапа подготовки?",
    "💭 Какой совет вы бы дали себе трёхмесячной давности?",
]

MEMORY_QUESTIONS_MID = [
    "💭 Какой момент подготовки принёс вам больше всего радости на этой неделе?",
    "💭 Что удивило вас больше всего в процессе подготовки?",
    "💭 За что вы благодарны друг другу сегодня?",
    "💭 Какой самый смешной/нелепый момент был на этой неделе?",
    "💭 Что вы уже сделали такого, чем гордитесь?",
]

MEMORY_QUESTIONS_LATE = [
    "💭 Что вы больше всего ждёте от дня свадьбы?",
    "💭 Как изменились ваши ожидания от свадьбы за время подготовки?",
    "💭 Что вы хотите сказать друг другу перед свадьбой, но пока не сказали?",
    "💭 Какой момент подготовки стал для вас неожиданно трогательным?",
    "💭 Что вы хотите запомнить о себе в этот период?",
]

MEMORY_QUESTIONS_FINAL = [
    "💭 Что вы чувствуете сегодня, за день до свадьбы?",
    "💭 Какой совет вы бы дали паре, которая только начинает подготовку?",
    "💭 Что самое важное вы поняли о себе и друг другу за время подготовки?",
    "💭 Какой момент вы уже сейчас представляете как 'наш будущий анекдот'?",
    "💭 Что вы хотите пожелать себе на завтра?",
]

async def send_daily_motivation(bot: Bot, chat_id: int):
    """Отправка персонализированного ежедневного мотивационного сообщения"""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Couple).where(Couple.chat_id == chat_id)
            )
            couple = result.scalar_one_or_none()
            
            if not couple:
                message = "🌅 Доброе утро! Готовитесь к свадьбе? Я помогу вам организовать всё без стресса 💍\nНапишите /start чтобы начать!"
                await bot.send_message(chat_id=chat_id, text=message)
                return
            
            days_left = (couple.wedding_date - datetime.now().date()).days
            
            # Выбираем набор сообщений в зависимости от этапа
            if days_left > 180:
                messages = DAILY_MESSAGES_EARLY
                prefix = f"👰🤵 {couple.partner1_name} и {couple.partner2_name}, у вас впереди целое приключение! "
            elif days_left > 60:
                messages = DAILY_MESSAGES_MID
                prefix = f"👰🤵 {couple.partner1_name} и {couple.partner2_name}, подготовка в самом разгаре! "
            elif days_left > 7:
                messages = DAILY_MESSAGES_LATE
                prefix = f"👰🤵 {couple.partner1_name} и {couple.partner2_name}, осталось совсем немного! "
            elif days_left > 0:
                messages = DAILY_MESSAGES_FINAL
                prefix = f"👰🤵 {couple.partner1_name} и {couple.partner2_name}, завтра большой день! "
            else:
                messages = DAILY_MESSAGES_WEDDING_DAY
                prefix = ""
            
            # Выбираем случайное сообщение из подходящего набора
            message = random.choice(messages)
            
            # Формируем финальное сообщение
            if days_left >= 0:
                full_message = f"🌅 <b>Доброе утро, будущие молодожёны!</b>\n\n{prefix}{message}\n\n<i>P.S. Не забудьте сегодня улыбнуться друг другу без повода 😊</i>"
            else:
                full_message = f"🌅 <b>Доброе утро, молодожёны!</b>\n\n{prefix}{message}\n\n<i>Спасибо, что доверили мне часть вашей подготовки. Желаю вам счастья! 💍</i>"
        
        await bot.send_message(
            chat_id=chat_id,
            text=full_message,
            parse_mode="HTML"
        )
        logger.info(f"💌 Ежедневная мотивация отправлена пользователю {chat_id} (дней до свадьбы: {days_left})")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки мотивации {chat_id}: {e}")

async def send_weekly_question(bot: Bot, chat_id: int):
    """Отправка еженедельного вопроса для Книги воспоминаний"""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Couple).where(Couple.chat_id == chat_id)
            )
            couple = result.scalar_one_or_none()
            
            if not couple:
                return
            
            days_left = (couple.wedding_date - datetime.now().date()).days
            
            # Выбираем набор вопросов по этапу
            if days_left > 180:
                questions = MEMORY_QUESTIONS_EARLY
            elif days_left > 60:
                questions = MEMORY_QUESTIONS_MID
            elif days_left > 7:
                questions = MEMORY_QUESTIONS_LATE
            else:
                questions = MEMORY_QUESTIONS_FINAL
            
            # Исключаем уже заданные вопросы
            result = await session.execute(
                select(Memory.question).where(Memory.couple_id == couple.id)
            )
            asked_questions = [row[0] for row in result.fetchall()]
            
            # Фильтруем новые вопросы
            new_questions = [q for q in questions if q not in asked_questions]
            if not new_questions:
                new_questions = questions
            
            question = random.choice(new_questions)
            
            # Сохраняем вопрос в БД (без ответа)
            memory = Memory(
                couple_id=couple.id,
                question=question,
                answer="",
                asked_at=datetime.now().date(),
                answered_at=None
            )
            session.add(memory)
            await session.commit()
            memory_id = memory.id
        
        # Отправляем вопрос
        text = (
            f"📖 <b>Книга воспоминаний</b>\n\n"
            f"{question}\n\n"
            f"Ваш ответ сохранится в нашу общую книгу и будет отправлен вам в день свадьбы как подарок 💍\n"
            f"<i>Ответьте одним сообщением в течение 48 часов</i>"
        )
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Ответить сейчас", callback_data=f"memory_answer_{memory_id}")]
        ])
        
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        logger.info(f"📖 Вопрос для книги воспоминаний отправлен пользователю {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки вопроса {chat_id}: {e}")

async def send_memories_book(bot: Bot, chat_id: int):
    """Отправка собранной Книги воспоминаний в день свадьбы"""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Couple).where(Couple.chat_id == chat_id)
            )
            couple = result.scalar_one_or_none()
            
            if not couple:
                return
            
            # Получаем все ответы пары
            result = await session.execute(
                select(Memory)
                .where(Memory.couple_id == couple.id)
                .where(Memory.answer != "")
                .order_by(Memory.asked_at)
            )
            memories = result.scalars().all()
            
            if not memories:
                text = (
                    "📖 <b>Ваша Книга воспоминаний</b>\n\n"
                    "К сожалению, вы не успели ответить на вопросы 😔\n"
                    "Но это не беда — ваша настоящая книга только начинается сегодня!\n\n"
                    "С ДНЁМ СВАДЬБЫ! 💍✨"
                )
            else:
                text = "📖 <b>Ваша Книга воспоминаний</b>\n\n"
                text += f"Дорогие {couple.partner1_name} и {couple.partner2_name}!\n\n"
                text += "Эти строки собраны за время вашей подготовки к свадьбе.\n"
                text += "Читайте их вместе — и вспоминайте путь, который вы прошли рука об руку 💫\n\n"
                text += "━" * 30 + "\n\n"
                
                for i, memory in enumerate(memories, 1):
                    date_str = memory.asked_at.strftime("%d.%m.%Y")
                    text += f"<b>{i}. {date_str}</b>\n"
                    text += f"Вопрос: {memory.question}\n"
                    text += f"Ваш ответ: {memory.answer}\n\n"
                    text += "─" * 30 + "\n\n"
                
                text += "━" * 30 + "\n\n"
                text += "💫 Сегодня вы начинаете новую главу своей книги.\n"
                text += "Пусть она будет наполнена любовью, смехом и счастьем!\n\n"
                text += "С ДНЁМ СВАДЬБЫ! 💍✨"
        
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML"
        )
        logger.info(f"📖 Книга воспоминаний отправлена паре {couple.id} в день свадьбы")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки книги воспоминаний {chat_id}: {e}")

async def schedule_task_reminders(bot: Bot, task_id: int, due_date: datetime.date, task_title: str, chat_id: int):
    """Планирование напоминаний для задачи"""
    now = datetime.now().date()
    is_critical = any(word in task_title.lower() for word in ["локация", "платье", "фотограф", "костюм"])
    
    # Первое напоминание: за 30 дней для критических, 14 для остальных
    first_days = 30 if is_critical else 14
    first_date = due_date - timedelta(days=first_days)
    if first_date > now:
        run_time = datetime.combine(first_date, datetime.min.time().replace(hour=10, minute=0))
        scheduler.add_job(
            lambda: bot.send_message(
                chat_id=chat_id,
                text=f"🗓️ <b>Планирование</b>\n\nЧерез {first_days} дней дедлайн по задаче:\n«{task_title}»\n\nНачните подготовку заранее — так спокойнее! 😊",
                parse_mode="HTML"
            ),
            trigger=DateTrigger(run_date=run_time),
            id=f"reminder_{task_id}_planning",
            replace_existing=True,
            misfire_grace_time=3600
        )
    
    # Второе напоминание: за 3 дня
    second_date = due_date - timedelta(days=3)
    if second_date > now:
        run_time = datetime.combine(second_date, datetime.min.time().replace(hour=10, minute=0))
        scheduler.add_job(
            lambda: bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ <b>Напоминание</b>\n\nЧерез 3 дня дедлайн по задаче:\n«{task_title}»\n\nСамое время заняться этим! ✨",
                parse_mode="HTML"
            ),
            trigger=DateTrigger(run_date=run_time),
            id=f"reminder_{task_id}_urgent",
            replace_existing=True,
            misfire_grace_time=3600
        )
    
    # Финальное напоминание: за 1 день
    final_date = due_date - timedelta(days=1)
    if final_date > now:
        run_time = datetime.combine(final_date, datetime.min.time().replace(hour=10, minute=0))
        scheduler.add_job(
            lambda: bot.send_message(
                chat_id=chat_id,
                text=f"⏰ <b>ФИНАЛЬНОЕ НАПОМИНАНИЕ!</b>\n\nЗавтра дедлайн по задаче:\n«{task_title}»\n\nНе забудьте завершить! 💍",
                parse_mode="HTML"
            ),
            trigger=DateTrigger(run_date=run_time),
            id=f"reminder_{task_id}_final",
            replace_existing=True,
            misfire_grace_time=3600
        )

async def schedule_wedding_day_reminder(bot: Bot, couple_id: int, wedding_date: datetime.date, chat_id: int):
    """Планирование напоминания на день свадьбы"""
    run_time = datetime.combine(wedding_date, datetime.min.time().replace(hour=9, minute=0))
    scheduler.add_job(
        send_memories_book,
        trigger=DateTrigger(run_date=run_time),
        args=[bot, chat_id],
        id=f"memories_book_{couple_id}",
        replace_existing=True,
        misfire_grace_time=3600
    )

async def restore_scheduled_reminders(bot: Bot):
    """Восстановление напоминаний после перезапуска бота"""
    logger.info("🔄 Восстанавливаю запланированные напоминания...")
    
    async with AsyncSessionLocal() as session:
        # Получаем все активные пары
        result = await session.execute(
            select(Couple).where(Couple.wedding_date >= datetime.now().date())
        )
        couples = result.scalars().all()
        
        restored_tasks = 0
        restored_motivations = 0
        restored_memories = 0
        
        for couple in couples:
            # 1. Восстанавливаем напоминания по задачам
            result = await session.execute(
                select(Task)
                .where(Task.couple_id == couple.id)
                .where(Task.is_completed == False)
            )
            tasks = result.scalars().all()
            
            for task in tasks:
                await schedule_task_reminders(bot, task.id, task.due_date, task.title, couple.chat_id)
                restored_tasks += 1
            
            # 2. Планируем ежедневную мотивацию (10:30 утра)
            job_id = f"daily_motivation_{couple.id}"
            if not scheduler.get_job(job_id):
                # Устанавливаем время 10:30 утра ежедневно
                next_run = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
                if datetime.now() > next_run:
                    next_run += timedelta(days=1)
                
                scheduler.add_job(
                    send_daily_motivation,
                    trigger=IntervalTrigger(days=1),
                    next_run_time=next_run,
                    args=[bot, couple.chat_id],
                    id=job_id,
                    replace_existing=True,
                    misfire_grace_time=3600
                )
                restored_motivations += 1
            
            # 3. Планируем еженедельные вопросы для Книги воспоминаний (каждую пятницу в 18:00)
            job_id_memories = f"weekly_memories_{couple.id}"
            if not scheduler.get_job(job_id_memories):
                # Определяем ближайшую пятницу в 18:00
                now = datetime.now()
                days_until_friday = (4 - now.weekday()) % 7  # 4 = пятница
                if days_until_friday == 0 and now.hour >= 18:
                    days_until_friday = 7
                
                first_friday = now + timedelta(days=days_until_friday)
                first_run = first_friday.replace(hour=18, minute=0, second=0, microsecond=0)
                
                scheduler.add_job(
                    send_weekly_question,
                    trigger=CronTrigger(day_of_week='fri', hour=18, minute=0),
                    next_run_time=first_run,
                    args=[bot, couple.chat_id],
                    id=job_id_memories,
                    replace_existing=True,
                    misfire_grace_time=7200
                )
                restored_memories += 1
            
            # 4. Планируем отправку Книги воспоминаний в день свадьбы
            job_id_book = f"memories_book_{couple.id}"
            if not scheduler.get_job(job_id_book):
                await schedule_wedding_day_reminder(bot, couple.id, couple.wedding_date, couple.chat_id)
        
        logger.info(f"✅ Восстановлено {restored_tasks} напоминаний для задач")
        logger.info(f"✅ Запланировано {restored_motivations} ежедневных мотиваций")
        logger.info(f"✅ Запланировано {restored_memories} еженедельных вопросов для Книги воспоминаний")
        logger.info(f"✅ Восстановлено {len(couples)} напоминаний о дне свадьбы")

async def main():
    # Инициализация БД
    await init_db()
    logger.info("✅ База данных инициализирована")
    
    # Инициализация бота
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Подключение роутеров
    from handlers import router as start_router
    dp.include_router(start_router)
    
    # Запуск планировщика
    scheduler.start()
    logger.info("⏰ Планировщик напоминаний запущен")
    
    # Восстановление напоминаний после перезапуска
    await restore_scheduled_reminders(bot)
    
    logger.info("✅ Бот запущен и готов к работе!")
    bot_info = await bot.get_me()
    logger.info(f"🤖 Имя бота: @{bot_info.username} (ID: {bot_info.id})")
    
    # Запуск поллинга
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Бот остановлен пользователем")
        scheduler.shutdown()