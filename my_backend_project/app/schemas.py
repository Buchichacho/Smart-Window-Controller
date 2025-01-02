from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int

    class Config:
        orm_mode = True


class DeviceBase(BaseModel):
    name: str
    state: str  # Состояние устройства
    auto_close_on_rain: bool
    auto_close_on_fire: bool
    timer_minutes: Optional[int]  # Таймер
    alarm_time: Optional[str]  # Будильник
    is_timed_action_pending: bool  # Отложенное действие


class DeviceCreate(BaseModel):
    name: str
    product_id: str
    product_password: str


class DeviceResponse(DeviceBase):
    id: int
    owner_id: int

    class Config:
        orm_mode = True


class DeviceControl(BaseModel):
    state: Optional[str] = Field(None, pattern="^(opened|closed)$")  # Состояние необязательно
    timer_minutes: Optional[int] = None  # Указываем значение по умолчанию
    alarm_time: Optional[str] = None  # Указываем значение по умолчанию

    class Config:
        schema_extra = {
            "example": {
                "state": "closed",
                "timer_minutes": 15,
                "alarm_time": "14:30",
            }
        }

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
