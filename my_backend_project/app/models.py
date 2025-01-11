from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float
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
    state = Column(String, default="opened")
    auto_close_on_rain = Column(Boolean, default=False)
    auto_close_on_fire = Column(Boolean, default=False)
    auto_regulate_temp = Column(Boolean, default=False)

    rain_alarm = Column(Boolean, default=False)
    fire_alarm = Column(Boolean, default=False)

    desired_temperature = Column(Float, nullable=True, default=None)
    desired_humidity = Column(Float, nullable=True, default=None)
    temp_unit = Column(String, nullable=True, default="C")
    current_temperature = Column(Float, nullable=True, default=None)
    current_humidity = Column(Float, nullable=True, default=None)
    outside_temperature = Column(Float, nullable=True, default=None)
    outside_humidity = Column(Float, nullable=True, default=None)

    timer_minutes = Column(Integer, nullable=True)
    alarm_time = Column(String, nullable=True)
    is_timed_action_pending = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(String, ForeignKey("product_devices.product_id"), nullable=False)

    owner = relationship("User", back_populates="devices")
    product_device = relationship("ProductDevice", backref="devices")

class ProductDevice(Base):
    __tablename__ = "product_devices"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, unique=True, nullable=False)
    product_password = Column(String, nullable=False)
    name = Column(String, nullable=True)
