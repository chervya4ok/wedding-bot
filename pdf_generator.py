import io
import logging
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime

# Настройка логгера для этого модуля
logger = logging.getLogger(__name__)

# РЕГИСТРИРУЕМ ШРИФТ С ПОДДЕРЖКОЙ КИРИЛЛИЦЫ (один раз, глобально)
try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    DEFAULT_FONT = 'DejaVuSans'
    logger.info("✅ Шрифт DejaVuSans успешно загружен из файла")
except Exception as e:
    DEFAULT_FONT = 'Helvetica'
    logger.warning(f"⚠️ Шрифт DejaVuSans не найден ({e}). Используется Helvetica")

def truncate_text(text, max_length=40):
    """Обрезаем текст для предотвращения переполнения ячеек таблицы"""
    if not text:
        return ""
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text

def generate_wedding_report(couple_data, tasks, expenses, guests):
    """
    Генерация PDF-отчёта о подготовке к свадьбе
    
    Args:
        couple_data: словарь с данными пары
        tasks: список задач
        expenses: список трат
        guests: список гостей
    
    Returns:
        io.BytesIO: буфер с PDF-файлом
    """
    buffer = io.BytesIO()
    
    # Создаём документ с правильными настройками
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=0.6*inch,
        bottomMargin=0.6*inch,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch
    )
    
    # Стили с правильным интерлиньяжем (предотвращает наложение текста)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=DEFAULT_FONT,
        fontSize=22,
        spaceAfter=14,
        textColor=colors.HexColor('#8B0000'),
        alignment=1,
        leading=26
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontName=DEFAULT_FONT,
        fontSize=14,
        spaceAfter=10,
        textColor=colors.HexColor('#5B2C6F'),
        alignment=1,
        leading=18
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName=DEFAULT_FONT,
        fontSize=15,
        spaceBefore=14,
        spaceAfter=8,
        textColor=colors.HexColor('#4A235A'),
        leading=20
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName=DEFAULT_FONT,
        fontSize=11,
        spaceAfter=6,
        leading=16
    )
    
    small_style = ParagraphStyle(
        'CustomSmall',
        parent=styles['Normal'],
        fontName=DEFAULT_FONT,
        fontSize=9,
        spaceAfter=4,
        leading=14
    )
    
    tip_style = ParagraphStyle(
        'CustomTip',
        parent=styles['Italic'],
        fontName=DEFAULT_FONT,
        fontSize=10,
        spaceAfter=8,
        textColor=colors.HexColor('#7B241C'),
        leading=14
    )
    
    footer_style = ParagraphStyle(
        'CustomFooter',
        parent=styles['Italic'],
        fontName=DEFAULT_FONT,
        fontSize=10,
        alignment=1,
        textColor=colors.HexColor('#8B0000'),
        leading=14
    )
    
    # Формируем контент
    content = []
    
    # ============ ТИТУЛЬНАЯ СТРАНИЦА ============
    content.append(Spacer(1, 0.4*inch))
    content.append(Paragraph("Свадьба без паники", title_style))
    content.append(Paragraph("Ваш персональный отчёт о подготовке", subtitle_style))
    content.append(Spacer(1, 0.5*inch))
    
    # Данные пары
    couple_info = [
        ["Пара", f"{couple_data['partner1_name']} и {couple_data['partner2_name']}"],
        ["Дата свадьбы", couple_data['wedding_date'].strftime('%d.%m.%Y')],
        ["До свадьбы", f"{couple_data['days_left']} дней"],
        ["Стиль свадьбы", couple_data['wedding_type']],
        ["Бюджет", f"{couple_data['budget_total']:,.0f} ₽"],
        ["Дата формирования", datetime.now().strftime('%d.%m.%Y')]
    ]
    
    couple_table = Table(couple_info, colWidths=[2.2*inch, 4*inch])
    couple_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F4ECF7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#4A235A')),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#D2B4DE')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    content.append(couple_table)
    content.append(Spacer(1, 0.4*inch))
    
    # Прогресс подготовки
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.is_completed)
    progress_percent = int(completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    content.append(Paragraph(f"Прогресс подготовки: {completed_tasks} из {total_tasks} задач ({progress_percent}%)", 
                           heading_style))
    
    # Текстовый прогресс-бар
    bar_length = 30
    filled = int(bar_length * progress_percent / 100)
    empty = bar_length - filled
    progress_bar = f"[{'█' * filled}{'░' * empty}] {progress_percent}%"
    content.append(Paragraph(progress_bar, normal_style))
    content.append(Spacer(1, 0.3*inch))
    
    # Статистика гостей
    total_guests = len(guests)
    confirmed_guests = sum(1 for g in guests if g.is_confirmed)
    declined_guests = sum(1 for g in guests if g.will_not_come)
    pending_guests = total_guests - confirmed_guests - declined_guests
    
    guest_stats = [
        ["Всего приглашено", f"{total_guests} гостей"],
        ["Подтвердили участие", f"{confirmed_guests} ({int(confirmed_guests/total_guests*100)}%)"],
        ["Отказались", f"{declined_guests} ({int(declined_guests/total_guests*100)}%)"],
        ["Ждут ответа", f"{pending_guests} ({int(pending_guests/total_guests*100)}%)"],
    ]
    
    guest_table = Table(guest_stats, colWidths=[2.5*inch, 3.7*inch])
    guest_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EBF5FB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#154360')),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#85C1E2')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    content.append(Paragraph("Статистика гостей", heading_style))
    content.append(guest_table)
    content.append(PageBreak())
    
    # ============ ЧЕК-ЛИСТ ЗАДАЧ ============
    content.append(Paragraph("Чек-лист подготовки", title_style))
    content.append(Spacer(1, 0.3*inch))
    
    if tasks:
        task_data = [["Статус", "Задача", "Дедлайн", "Категория"]]
        for task in sorted(tasks, key=lambda x: x.due_date):
            status = "Выполнено" if task.is_completed else "В процессе"
            due_date = task.due_date.strftime('%d.%m.%Y')
            days_left = (task.due_date - datetime.now().date()).days
            
            if days_left < 0:
                due_date += " (просрочено)"
            elif days_left <= 3:
                due_date += f" (через {days_left} дн.)"
            
            task_data.append([
                status,
                truncate_text(task.title, 35),
                due_date,
                task.category.capitalize()
            ])
        
        task_table = Table(task_data, colWidths=[1.2*inch, 2.8*inch, 1.5*inch, 1.5*inch])
        task_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F9E79F')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#7D6608')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#F4D03F')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        content.append(task_table)
    else:
        content.append(Paragraph("Нет задач", normal_style))
    
    content.append(PageBreak())
    
    # ============ БЮДЖЕТ ============
    content.append(Paragraph("Детализация бюджета", title_style))
    content.append(Spacer(1, 0.3*inch))
    
    if expenses:
        # Группируем по категориям
        categories = {}
        for expense in expenses:
            cat = expense.category
            categories[cat] = categories.get(cat, 0) + expense.amount
        
        budget_total = couple_data['budget_total']
        budget_data = [["Категория", "Потрачено", "Процент"]]
        
        # Сортируем категории по сумме
        for cat, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            percent = amount / budget_total * 100 if budget_total > 0 else 0
            budget_data.append([
                cat.capitalize(),
                f"{amount:,.0f} ₽",
                f"{percent:.0f}%"
            ])
        
        # Итоговая строка
        total_spent = sum(categories.values())
        total_percent = total_spent / budget_total * 100 if budget_total > 0 else 0
        budget_data.append([
            "ИТОГО",
            f"{total_spent:,.0f} ₽",
            f"{total_percent:.0f}%"
        ])
        
        budget_table = Table(budget_data, colWidths=[2.5*inch, 2*inch, 1.7*inch])
        budget_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D5F4E6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0B5345')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#76D7C4')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#A3E4D7')),
            ('FONTNAME', (0, -1), (-1, -1), DEFAULT_FONT),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#0B5345')),
        ]))
        content.append(budget_table)
    else:
        content.append(Paragraph("Нет записанных трат", normal_style))
    
    content.append(Spacer(1, 0.4*inch))
    content.append(Paragraph(
        "Совет: распечатайте этот отчёт для встречи с родителями или свадебным организатором!",
        tip_style
    ))
    content.append(PageBreak())
    
    # ============ ГОСТИ ============
    content.append(Paragraph("Список гостей", title_style))
    content.append(Spacer(1, 0.3*inch))
    
    if guests:
        guest_data = [["Статус", "Имя", "Контакт", "Пожелания"]]
        for guest in sorted(guests, key=lambda x: x.name):
            if guest.is_confirmed:
                status = "Подтверждён"
            elif guest.will_not_come:
                status = "Не придёт"
            else:
                status = "Ожидает ответа"
            
            contact = guest.phone or guest.email or "—"
            notes = guest.dietary_notes or "—"
            if guest.has_plus_one and guest.plus_one_name:
                notes += f" (+1: {guest.plus_one_name})"
            
            guest_data.append([
                status,
                guest.name,
                truncate_text(contact, 18),
                truncate_text(notes, 25)
            ])
        
        guest_table = Table(guest_data, colWidths=[1.5*inch, 1.8*inch, 1.8*inch, 2.5*inch])
        guest_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FADBD8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#78281F')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), DEFAULT_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#F1948A')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        content.append(guest_table)
    else:
        content.append(Paragraph("Нет добавленных гостей", normal_style))
    
    content.append(Spacer(1, 0.6*inch))
    content.append(Paragraph(
        "С любовью, ваш свадебный помощник",
        footer_style
    ))
    
    # Собираем PDF
    doc.build(content)
    buffer.seek(0)
    return buffer