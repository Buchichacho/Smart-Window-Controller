import os

# URL базы данных
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://myuser:mypassword@localhost/mydatabase")

# Конфигурация для JWT
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")  # Лучше использовать переменные окружения для безопасности
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
