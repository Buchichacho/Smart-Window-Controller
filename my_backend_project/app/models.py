from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)

    devices = relationship("Device", back_populates="owner")

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    state = Column(String, default="opened")  # Поле состояния окна
    auto_close_on_rain = Column(Boolean, default=False)
    auto_close_on_fire = Column(Boolean, default=False)
    timer_minutes = Column(Integer, nullable=True)  # Таймер
    alarm_time = Column(String, nullable=True)  # Будильник
    is_timed_action_pending = Column(Boolean, default=False)  # Флаг действия по таймеру
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="devices")



class ProductDevice(Base):
    __tablename__ = "product_devices"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, unique=True, nullable=False)
    product_password = Column(String, nullable=False)
    name = Column(String, nullable=True)
