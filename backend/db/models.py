from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    transcript = Column(String)
    clarification_question = Column(String, nullable=True)
    anomaly_alert = Column(String, nullable=True)
    tomorrow_tip = Column(String, nullable=True)
    total_profit = Column(Float)

    sales = relationship("SalesItem", back_populates="ledger_entry")
    expenses = relationship("ExpenseItem", back_populates="ledger_entry")

class SalesItem(Base):
    __tablename__ = "sales_items"

    id = Column(Integer, primary_key=True, index=True)
    ledger_id = Column(Integer, ForeignKey("ledger_entries.id"))
    item = Column(String)
    qty = Column(String)
    price = Column(Float)
    uncertain = Column(Boolean, default=False)

    ledger_entry = relationship("LedgerEntry", back_populates="sales")

class ExpenseItem(Base):
    __tablename__ = "expense_items"

    id = Column(Integer, primary_key=True, index=True)
    ledger_id = Column(Integer, ForeignKey("ledger_entries.id"))
    type = Column(String)
    amount = Column(Float)

    ledger_entry = relationship("LedgerEntry", back_populates="expenses")
