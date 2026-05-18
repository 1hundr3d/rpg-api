from database import engine, Base

print("Создаём таблицы...")
Base.metadata.create_all(bind=engine)
print("Готово!")