from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import engine, get_db, Base
from app.models import Base, ProductDevice
from app.routers import devices
from app.auth import auth_router

# Создание всех таблиц
Base.metadata.create_all(bind=engine)

# Инициализация приложения FastAPI
app = FastAPI()

# Настройки CORS
origins = [
    "http://localhost",
    "http://localhost:3000",  # Для React или другого фронтен
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение маршрутов
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(devices.router, prefix="/devices", tags=["devices"])

# Тестовый маршрут
@app.get("/")
def root():
    return {"message": "Welcome to the IoT Controller API"}

def initialize_test_data():
    db: Session = next(get_db())
    test_device = db.query(ProductDevice).filter_by(product_id="123456").first()
    if not test_device:
        new_device = ProductDevice(
            product_id="123456",
            product_password="securepassword",
            name="Test Device"
        )
        db.add(new_device)
        db.commit()
        db.refresh(new_device)
        print("Test device added:", new_device)

initialize_test_data()