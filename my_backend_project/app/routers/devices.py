from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Device, User, ProductDevice
from app.schemas import DeviceCreate, DeviceResponse, DeviceControl
from app.auth import get_current_user
from app.database import SessionLocal

import json
import time
from datetime import datetime, timedelta
import threading
import requests
# Подключаем библиотеку paho-mqtt
from paho.mqtt import client as mqtt_client

router = APIRouter()

BROKER = "147.232.205.176"  # Адрес брокера MQTT
PORT = 1883
TOPIC_PREFIX = "kpi/caprica/smart_window/"
CLIENT_ID = "server_controller"
USERNAME = "maker"
PASSWORD = "mother.mqtt.password"

# Храним таймеры для каждого устройства: {product_id: threading.Timer()}
device_timers = {}

#############################################################################
# НАСТРАИВАЕМ MQTT ОДИН РАЗ
#############################################################################

mqtt_client_instance = mqtt_client.Client(client_id=CLIENT_ID, userdata=None, protocol=mqtt_client.MQTTv311)
mqtt_client_instance.username_pw_set(USERNAME, PASSWORD)
# mqtt_client_instance.clean_session = False  # <-- Можно включить, если нужна сохранённая сессия
mqtt_client_instance.connect(BROKER, PORT)  # keepalive=60 (или 5)


def publish_message(topic: str, message: dict, retain_status: bool):
    """
    Публикуем JSON-сообщение в топик MQTT и выводим отладку в консоль.
    """
    payload = json.dumps(message)
    print(f"Published message to topic {topic}: {payload}")
    # retain=True можно включить, если нужно, чтобы устройство после перезагрузки
    # прочитало последнюю команду. Иначе ставим retain=False.
    mqtt_client_instance.publish(topic, payload, qos=1, retain=retain_status)


def on_mqtt_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected with result code {rc}")

    # Подписываемся на все интересующие нас топики
    # "+" вместо конкретного product_id позволяет принимать сообщения
    # от всех устройств, если нужно.
    status_topic = f"{TOPIC_PREFIX}+/status"
    inside_temp_topic = f"{TOPIC_PREFIX}+/inside_temperature"
    inside_hum_topic = f"{TOPIC_PREFIX}+/inside_humidity"
    outside_temp_topic = f"{TOPIC_PREFIX}+/outside_temperature"
    outside_hum_topic = f"{TOPIC_PREFIX}+/outside_humidity"

    client.subscribe(status_topic, qos=1)
    client.subscribe(inside_temp_topic, qos=1)
    client.subscribe(inside_hum_topic, qos=1)
    client.subscribe(outside_temp_topic, qos=1)
    client.subscribe(outside_hum_topic, qos=1)

    print(f"[MQTT] Subscribed to topics: {status_topic}, {inside_temp_topic}, {inside_hum_topic}, {outside_temp_topic}, {outside_hum_topic}")

def on_mqtt_message(client, userdata, msg):
    try:
        topic_str = msg.topic
        if isinstance(topic_str, bytes):
            topic_str = topic_str.decode("utf-8")

        payload_str = msg.payload
        if isinstance(payload_str, bytes):
            payload_str = payload_str.decode("utf-8")

        payload = json.loads(payload_str)
        print(f"[MQTT] Received message on {topic_str}: {payload}")

        product_id = payload.get("product_id")
        if not product_id:
            # Если в JSON нет product_id, то не сможем привязать к Device
            print("[MQTT] No product_id in payload, skipping")
            return

        db = SessionLocal()
        try:
            device = db.query(Device).filter_by(product_id=product_id).first()
            if not device:
                print(f"[DB] No device found with product_id={product_id}")
                return

            status_str = payload.get("status")
            state = payload.get("state")
            if status_str == "success" and state:
                device.state = state
                device.is_timed_action_pending = False
                db.commit()
                db.refresh(device)
                print(f"[DB] Device {device.id} updated state to {state}")

            if topic_str.endswith("/inside_temperature"):
                inside_temp = payload.get("temperature")
                if inside_temp is not None:
                    device.current_temperature = float(inside_temp)
                    db.commit()
                    db.refresh(device)
                    print(f"[DB] Device {device.id} updated INSIDE temperature => {inside_temp}")

            elif topic_str.endswith("/inside_humidity"):
                inside_hum = payload.get("humidity")
                if inside_hum is not None:
                    device.current_humidity = float(inside_hum)
                    db.commit()
                    db.refresh(device)
                    print(f"[DB] Device {device.id} updated INSIDE humidity => {inside_hum}")

            elif topic_str.endswith("/outside_temperature"):
                outside_temp = payload.get("temperature")
                if outside_temp is not None:
                    device.outside_temperature = float(outside_temp)
                    db.commit()
                    db.refresh(device)
                    print(f"[DB] Device {device.id} updated OUTSIDE temperature => {outside_temp}")

            elif topic_str.endswith("/outside_humidity"):
                outside_hum = payload.get("humidity")
                if outside_hum is not None:
                    device.outside_humidity = float(outside_hum)
                    db.commit()
                    db.refresh(device)
                    print(f"[DB] Device {device.id} updated OUTSIDE humidity => {outside_hum}")

            # Обновляем тревоги, если пришли
            if "rain_alarm" in payload:
                device.rain_alarm = bool(payload["rain_alarm"])
                db.commit()
                db.refresh(device)
                print(f"[DB] Device {device.id} updated rain_alarm => {device.rain_alarm}")

            if "fire_alarm" in payload:
                device.fire_alarm = bool(payload["fire_alarm"])
                db.commit()
                db.refresh(device)
                print(f"[DB] Device {device.id} updated fire_alarm => {device.fire_alarm}")

        except Exception as e:
            db.rollback()
            print("[MQTT] DB error:", e)
        finally:
            db.close()

    except Exception as e:
        print("[MQTT] Error processing message:", e)


mqtt_client_instance.on_connect = on_mqtt_connect
mqtt_client_instance.on_message = on_mqtt_message


def start_mqtt_loop():
    mqtt_client_instance.loop_forever()


mqtt_thread = threading.Thread(target=start_mqtt_loop, daemon=True)
mqtt_thread.start()


#############################################################################
# ФУНКЦИЯ ДЛЯ ПЕРИОДИЧЕСКИХ "ПИНГУЮЩИХ" ЗАПРОСОВ
#############################################################################

def ping_server_periodically():
    while True:
        try:
            requests.get("http://localhost:8000")
        except Exception as e:
            print("[PING] Could not ping server:", e)
        time.sleep(5)


# Запускаем «пингующий» поток
ping_thread = threading.Thread(target=ping_server_periodically, daemon=True)
ping_thread.start()


#############################################################################
# ENDPOINTS FASTAPI
#############################################################################

@router.post("/", response_model=DeviceResponse)
def add_device(
        device: DeviceCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):

    # Проверяем, что устройство вообще существует в таблице ProductDevice
    product_device = db.query(ProductDevice).filter_by(
        product_id=device.product_id,
        product_password=device.product_password,
    ).first()
    if not product_device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device with the specified Product ID and Password not found",
        )

    existing_device = db.query(Device).filter_by(product_id=device.product_id).first()
    if existing_device:
        # Проверяем, добавлено ли оно текущим пользователем
        if existing_device.owner_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device with this Product ID is already added to your account",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device with this Product ID is already added by another user",
            )

    # Проверяем, нет ли такого же имени у текущего пользователя
    if db.query(Device).filter_by(owner_id=current_user.id, name=device.name).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device with this name already exists in your account",
        )

    new_device = Device(
        name=device.name,
        product_id=product_device.product_id,
        state="closed",
        auto_close_on_rain=False,
        auto_close_on_fire=False,
        auto_regulate_temp=False,
        owner_id=current_user.id,
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    return new_device


@router.get("/", response_model=list[DeviceResponse])
def get_user_devices(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    return db.query(Device).filter(Device.owner_id == current_user.id).all()


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(
        device_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id, Device.owner_id == current_user.id).first()
    if not device:
        raise HTTPException(404, "Device not found")
    return device


@router.delete("/{device_id}", status_code=204)
def delete_device(
        device_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id, Device.owner_id == current_user.id).first()
    if not device:
        raise HTTPException(404, "Device not found")

    db.delete(device)
    db.commit()
    return {"detail": "Device deleted"}


#############################################################################
# ОБРАБОТКА УПРАВЛЕНИЯ УСТРОЙСТВОМ (С ТАЙМЕРОМ/БУДИЛЬНИКОМ)
#############################################################################

# ===================== ВАЖНО: лишь фрагмент, замените в файле devices.py =====================


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

    # Проверяем, что state либо "opened", либо "closed"
    if not device_control.state:
        raise HTTPException(400, detail="State is required ('opened' or 'closed')")

    # Если задан таймер или будильник
    if device_control.timer_minutes or device_control.alarm_time:
        device.is_timed_action_pending = True

        # Если пользователь указал timer_minutes
        if device_control.timer_minutes:
            device.timer_minutes = device_control.timer_minutes
            device.alarm_time = None  # сбрасываем, чтобы в ответе было null
            delay = device.timer_minutes * 60

        # Если пользователь указал alarm_time
        elif device_control.alarm_time:
            device.alarm_time = device_control.alarm_time
            device.timer_minutes = None  # сбрасываем, чтобы в ответе было null

            alarm_time_dt = datetime.strptime(device_control.alarm_time, "%H:%M").time()
            now = datetime.now() + timedelta(hours=1)
            execute_time = datetime.combine(now.date(), alarm_time_dt)
            if execute_time < now:
                execute_time += timedelta(days=1)
            delay = (execute_time - now).total_seconds()

        product_id = device.product_id

        if product_id in device_timers:
            device_timers[product_id].cancel()

        # Создаём новый поток таймера
        timer = threading.Timer(delay, delayed_action, [product_id, device_control.state])
        timer.start()
        device_timers[product_id] = timer
        print(f"Timer on {device.product_id} started. {delay} remains seconds until alarm close window")

        db.commit()
        db.refresh(device)
        return device

    else:
        # НЕМЕДЛЕННОЕ ДЕЙСТВИЕ
        # Если текущее состояние уже такое и нет pending, выдаём ошибку
        if device_control.state == device.state and not device.is_timed_action_pending:
            raise HTTPException(400, detail=f"Device is already {device.state}.")

        device.state = device_control.state
        device.is_timed_action_pending = False

        # Сбрасываем timer_minutes / alarm_time, так как действие мгновенное
        device.timer_minutes = None
        device.alarm_time = None

        db.commit()
        db.refresh(device)

        # Публикуем действие в MQTT
        publish_message(f"{TOPIC_PREFIX}{device.product_id}/action", {"state": device_control.state}, False)
        return device


def delayed_action(product_id: str, new_state: str):
    """
    Функция, которую вызывают потоки-таймеры.
    1) Берёт device из БД
    2) Меняет device.state -> new_state
    3) Сбрасывает device.timer_minutes / device.alarm_time => None
    4) Отправляет MQTT-сообщение
    """
    db = next(get_db())
    device = db.query(Device).filter_by(product_id=product_id).first()
    if not device:
        return  # Устройство могло быть удалено

    # Меняем состояние, сбрасываем таймеры
    device.state = new_state
    device.is_timed_action_pending = False
    device.timer_minutes = None
    device.alarm_time = None

    db.commit()
    db.refresh(device)

    # Публикуем команду на устройство
    publish_message(f"{TOPIC_PREFIX}{product_id}/action", {"state": new_state}, False)
    print(f"[TIMER] Executed action for product_id={product_id} with state={new_state}")


def execute_action(product_id, state):
    publish_message(f"{TOPIC_PREFIX}{product_id}/action", {"state": state}, False)
    print(f"[TIMER] Executed action for product_id={product_id} with state={state}")


#############################################################################
# НАСТРОЙКИ: /devices/{device_id}/settings
#############################################################################

@router.put("/{device_id}/settings", response_model=DeviceResponse)
def update_device_settings(
        device_id: int,
        auto_regulate_temp: bool = None,
        auto_close_on_rain: bool = None,
        auto_close_on_fire: bool = None,
        desired_temperature: float = None,
        desired_humidity: float = None,
        temp_unit: str = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id, Device.owner_id == current_user.id).first()
    if not device:
        raise HTTPException(404, "Device not found")

    if auto_regulate_temp is not None:
        device.auto_regulate_temp = auto_regulate_temp
    if auto_close_on_rain is not None:
        device.auto_close_on_rain = auto_close_on_rain
    if auto_close_on_fire is not None:
        device.auto_close_on_fire = auto_close_on_fire
    if desired_temperature is not None:
        device.desired_temperature = desired_temperature
    if desired_humidity is not None:
        device.desired_humidity = desired_humidity
    if temp_unit is not None:
        device.temp_unit = temp_unit

    db.commit()
    db.refresh(device)

    pub_data = {
        "auto_regulate_temp": device.auto_regulate_temp,
        "auto_close_on_rain": device.auto_close_on_rain,
        "auto_close_on_fire": device.auto_close_on_fire,
    }
    # Добавим в сообщение лишь если не None
    if device.desired_temperature is not None:
        pub_data["desired_temperature"] = device.desired_temperature
    if device.desired_humidity is not None:
        pub_data["desired_humidity"] = device.desired_humidity
    if device.temp_unit:
        pub_data["temp_unit"] = device.temp_unit

    publish_message(f"{TOPIC_PREFIX}{device.product_id}/settings", pub_data, True)

    return device
