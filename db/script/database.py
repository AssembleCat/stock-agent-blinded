from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.script.models import Base

DATABASE_URL = "sqlite:///./market.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

if __name__ == "__main__":
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
