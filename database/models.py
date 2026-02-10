from sqlalchemy import Column, Integer, String, Date, Boolean, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Couple(Base):
    __tablename__ = "couples"
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True, nullable=False)  # Основной партнёр
    partner_chat_id = Column(Integer, nullable=True)  # Второй партнёр (опционально)
    share_token = Column(String(32), unique=True, nullable=True)  # Токен для приглашения
    partner1_name = Column(String, nullable=False)
    partner2_name = Column(String, nullable=False)
    wedding_date = Column(Date, nullable=False)
    wedding_type = Column(String)
    budget_total = Column(Float, default=0.0)
    created_at = Column(Date)
    
    tasks = relationship("Task", back_populates="couple", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="couple", cascade="all, delete-orphan")
    guests = relationship("Guest", back_populates="couple", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="couple", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True)
    couple_id = Column(Integer, ForeignKey("couples.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(String)
    due_date = Column(Date)
    category = Column(String)
    is_completed = Column(Boolean, default=False)
    days_before_wedding = Column(Integer)
    
    couple = relationship("Couple", back_populates="tasks")

class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True)
    couple_id = Column(Integer, ForeignKey("couples.id"), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String)
    date = Column(Date, default=datetime.now().date)
    
    couple = relationship("Couple", back_populates="expenses")

class Guest(Base):
    """Гости свадьбы"""
    __tablename__ = "guests"
    
    id = Column(Integer, primary_key=True)
    couple_id = Column(Integer, ForeignKey("couples.id"), nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String)
    email = Column(String)
    is_confirmed = Column(Boolean, default=False)
    will_not_come = Column(Boolean, default=False)
    has_plus_one = Column(Boolean, default=False)
    plus_one_name = Column(String)
    dietary_notes = Column(String)
    table_number = Column(Integer)
    created_at = Column(Date, default=datetime.now().date)
    
    couple = relationship("Couple", back_populates="guests")

class Memory(Base):
    """Воспоминания пары о подготовке к свадьбе"""
    __tablename__ = "memories"
    
    id = Column(Integer, primary_key=True)
    couple_id = Column(Integer, ForeignKey("couples.id"), nullable=False)
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)
    asked_at = Column(Date, default=datetime.now().date)
    answered_at = Column(Date)
    
    couple = relationship("Couple", back_populates="memories")