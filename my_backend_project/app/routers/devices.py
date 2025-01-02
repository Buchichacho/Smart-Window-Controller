from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Device, User, ProductDevice
from app.schemas import DeviceCreate, DeviceResponse, DeviceControl
from app.auth import get_current_user

router = APIRouter()

@router.post("/", response_model=DeviceResponse)
def add_device(
        device: DeviceCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    # Проверяем, существует ли устройство в таблице ProductDevice
    product_device = db.query(ProductDevice).filter_by(
        product_id=device.product_id,
        product_password=device.product_password,
    ).first()
    if not product_device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device with the specified Product ID and Password not found",
        )

    # Проверяем, используется ли заданное имя в учетной записи пользователя
    if db.query(Device).filter_by(owner_id=current_user.id, name=device.name).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device with this name already exists in your account",
        )

    # Добавляем устройство в пользовательское пространство
    new_device = Device(
        name=device.name,  # Используем имя, заданное пользователем
        auto_close_on_rain=False,
        auto_close_on_fire=False,
        owner_id=current_user.id,
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    return new_device


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(
        device_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    # Проверяем, существует ли устройство, принадлежащее текущему пользователю
    device = db.query(Device).filter(Device.id == device_id, Device.owner_id == current_user.id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )

    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
        device_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    # Проверяем, существует ли устройство, принадлежащее текущему пользователю
    device = db.query(Device).filter(Device.id == device_id, Device.owner_id == current_user.id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )

    # Удаляем устройство
    db.delete(device)
    db.commit()
    return {"detail": "Device deleted"}

@router.get("/", response_model=list[DeviceResponse])
def get_user_devices(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return db.query(Device).filter(Device.owner_id == current_user.id).all()

@router.post("/{device_id}/control", response_model=DeviceResponse)
def control_device(
    device_id: int,
    device_control: DeviceControl,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id, Device.owner_id == current_user.id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Проверка текущего состояния устройства
    if device_control.state:
        if device_control.state == device.state and not device.is_timed_action_pending:
            raise HTTPException(
                status_code=400,
                detail=f"Device is already {device.state}. You cannot perform the same action."
            )

        # Если запрос на действие без таймера или будильника
        if device_control.timer_minutes is None and device_control.alarm_time is None:
            # Сбрасываем отложенные действия
            device.is_timed_action_pending = False
            device.timer_minutes = None
            device.alarm_time = None
            device.state = device_control.state
            print(f"Device {device.name} is now {device.state}.")
        else:
            # Обновляем таймер или будильник
            device.state = device_control.state
            device.is_timed_action_pending = True
            if device_control.timer_minutes is not None:
                device.timer_minutes = device_control.timer_minutes
                device.alarm_time = None
                print(f"Device {device.name} will be {device.state} in {device_control.timer_minutes} minutes.")
            elif device_control.alarm_time is not None:
                device.alarm_time = device_control.alarm_time
                device.timer_minutes = None
                print(f"Device {device.name} will be {device.state} at {device_control.alarm_time}.")

    db.commit()
    db.refresh(device)
    return device

@router.put("/{device_id}/settings", response_model=DeviceResponse)
def update_device_settings(
    device_id: int,
    auto_close_on_rain: bool,
    auto_close_on_fire: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id, Device.owner_id == current_user.id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.auto_close_on_rain = auto_close_on_rain
    device.auto_close_on_fire = auto_close_on_fire
    db.commit()
    db.refresh(device)
    return device
