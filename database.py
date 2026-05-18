from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")

if DATABASE_URL is None:
    raise ValueError("DATABASE_URL is not set! Please add it to Render environment variables.")

if SECRET_KEY is None:
    raise ValueError("SECRET_KEY is not set! Please add it to Render environment variables.")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class HeroDB(Base):
    __tablename__ = 'heroes'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    hp = Column(Integer, default = 50)
    max_hp = Column(Integer, default = 50)
    atk = Column(Integer, default = 8)
    defense = Column(Integer, default = 2)
    gold = Column(Integer, default = 20)
    potions = Column(Integer, default = 2)
    level = Column(Integer, default = 1)
    exp = Column(Integer, default = 0)
    exp_to_next = Column(Integer, default = 10)
    description = Column(String, default = '')

class UserDB(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Integer, default=1) #1 - не заблокирован

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()