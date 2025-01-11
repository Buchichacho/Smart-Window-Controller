from sqlalchemy.orm import Session
from app.database import SessionLocal
import models

def init_db():
    db: Session = SessionLocal()

    # Инициализация базы данных
    models.Base.metadata.create_all(bind=db.get_bind())

    db.close()

if __name__ == "__main__":
    init_db()
