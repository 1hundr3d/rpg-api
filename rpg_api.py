from sqlalchemy.orm import Session
from database import HeroDB, UserDB, get_db, init_db
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.testclient import TestClient
from fastapi import WebSocket, WebSocketDisconnect
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import Optional
import random
import time
import logging
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
from dotenv import load_dotenv
from sqlalchemy import inspect
from cache import get_cache, set_cache

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")

# Константы баланса для игрового процесса
HEAL_AMOUNT = 30  # Количество здоровья, восстанавливаемое зельем
FLEE_CHANCE = 0.5  # Шанс успешного побега из боя
EXP_MULTIPLIER = 1.5  # Множитель опыта для следующего уровня
LEVEL_HP_BONUS = 10  # Бонус здоровья за уровень
LEVEL_ATK_BONUS = 2  # Бонус атаки за уровень
LEVEL_DEF_BONUS = 1  # Бонус защиты за уровень

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

from game_engine import Hero, Enemy


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Контекстный менеджер для управления жизненным циклом приложения.

    Выполняет загрузку данных при запуске сервера и сохранение при остановке.
    """
    # Код, выполняемый при запуске сервера
    logger.info("Сервер запускается . . .")
    init_db()
    yield
    # Код, выполняемый при выключении сервера
    logger.info("Сервер выключается . . .")


app = FastAPI(title="RPG + FastAPI", lifespan=lifespan)


@app.websocket("/ws/echo")
async def websocket_echo(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket соединение установлено")

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Получено сообщение {data}")

            await websocket.send_text(f"Эхо: {data}")
    except WebSocketDisconnect:
        logger.info("Соединение WebSocket закрыто.")


active_connections: list[WebSocket] = []


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"Клиент подключился. Всего подключений: {len(active_connections)}")

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Соощение: {data}")

            for conn in active_connections:
                await conn.send_text(f"💬 {data}")
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(
            f"Клиент отключился. Всего активных подключений: {len(active_connections)}"
        )

        for conn in active_connections:
            await conn.send_text(
                f"Пользоватеот отключился. Всего подключений: {len(active_connections)}"
            )


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login2")

request_counter = 0


class RequestCounterMiddleware(BaseHTTPMiddleware):
    """Middleware для подсчета количества запросов."""

    async def dispatch(self, request: Request, call_next):
        global request_counter
        request_counter += 1
        request.state.request_number = request_counter
        response = await call_next(request)
        response.headers["X-Request-Number"] = str(request_counter)
        return response


app.add_middleware(RequestCounterMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware для логирования запросов."""
    start_time = time.perf_counter()
    logger.info(f"{request.method} {request.url.path} - начат")
    response = await call_next(request)
    duration = time.perf_counter() - start_time
    logger.info(
        f"{request.method} {request.url.path} - завершен за {duration:.4f} сек."
    )
    return response


# Глобальное хранилище для врагов (в памяти программы)
# Примечание: Герои теперь хранятся в SQL базе данных через SQLAlchemy
database: dict[str, Enemy] = {}  # Ключ: "имя_героя_enemy", Значение: текущий враг

enemy_pool = [
    {"name": "Гоблин", "hp": 20, "atk": 8, "gold_reward": 10, "exp_reward": 5},
    {"name": "Орк", "hp": 35, "atk": 12, "gold_reward": 20, "exp_reward": 10},
    {"name": "Скелет", "hp": 15, "atk": 10, "gold_reward": 8, "exp_reward": 4},
    {"name": "Тролль", "hp": 50, "atk": 15, "gold_reward": 35, "exp_reward": 20},
]

# ========== НАСТРОЙКИ JWT И ПАРОЛЕЙ ==========

# Секретный ключ для подписи токенов.
SECRET_KEY = "mysecretkey1234567890"

# Алгоритм шифрования подписи
ALGORITHM = "HS256"

# Время жизни токена в минутах
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Настройка хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ========== ФУНКЦИИ ДЛЯ ПАРОЛЕЙ ==========


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ========== ФУНКЦИИ ДЛЯ СОЗДАНИЯ ТОКЕНА ==========


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# ========== МОДЕЛИ ДЛЯ АУТЕНТИФИКАЦИИ ==========
class UserCreate(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserLogin(BaseModel):
    username: str
    password: str


class CreateHeroRequest(BaseModel):
    """Запрос на создание героя. Содержит имя персонажа."""

    name: str


class ActionHeroRequest(BaseModel):
    """Запрос на выполнение действия в бою. Содержит имя героя и действие."""

    name: str
    action: str


class GameState(BaseModel):
    """Состояние игры. Используется как модель ответа для битв и создания персонажа.

    Поля enemy_name и enemy_hp являются опциональными и заполняются только во время боя.
    """

    hero_name: str
    hero_hp: int
    hero_max_hp: int
    enemy_name: Optional[str] = None
    enemy_hp: Optional[int] = None
    message: str


class HeroStats(BaseModel):
    """Статистика героя. Используется для вывода основной информации о персонаже."""

    name: str
    hp: int
    max_hp: int
    gold: int


def generate_enemy() -> Enemy:
    """Генерирует случайного врага из пула."""
    base = random.choice(enemy_pool)
    return Enemy(
        base["name"],
        base["hp"],
        base["atk"],
        base["gold_reward"],
        base["exp_reward"],
    )


def write_battle_log(hero_name: str, action: str, result: str, enemy_name: str = None):
    """Записывает результат боя в лог-файл.

    Args:
        hero_name: Имя героя, участвовавшего в бою.
        action: Действие, которое привело к результату (attack, potion, flee).
        result: Результат действия (victory, death, success, failed, etc.).
        enemy_name: Имя врага (опционально).
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open("battle_log.txt", "a", encoding="utf-8") as f:
        log_entry = f"[{timestamp}] Герой: {hero_name} | Действие: {action}"
        if enemy_name:
            log_entry += f" | Враг: {enemy_name}"
        log_entry += f" | Результат: {result}"
        f.write(log_entry + "\n")


# ========== ЗАВИСИМОСТИ ==========
def get_hero_by_name(hero_name: str, db: Session = Depends(get_db)) -> Hero:
    """Получить героя по имени из SQL базы данных. Если не существует - вызвать ошибку 404.

    Примечание: Ранее герои хранились в словаре database, теперь используется SQLAlchemy ORM.
    """
    # Запрос к SQL базе данных вместо работы со словарем database
    hero_db = db.query(HeroDB).filter(HeroDB.name == hero_name).first()
    if not hero_db:
        logger.error(f"Герой не найден: {hero_name}")
        raise HTTPException(status_code=404, detail="Персонаж не найден")

    # Создаем объект Hero и заполняем данными из SQL базы
    hero = Hero(hero_db.name)
    hero.hp = hero_db.hp
    hero.max_hp = hero_db.max_hp
    hero.atk = hero_db.atk
    hero.defense = hero_db.defense
    hero.gold = hero_db.gold
    hero.potions = hero_db.potions
    hero.level = hero_db.level
    hero.exp = hero_db.exp
    hero.exp_to_next = hero_db.exp_to_next

    return hero


def get_alive_hero(hero_name: str, db: Session = Depends(get_db)) -> Hero:
    """Получить живого героя из SQL базы данных. Если мертв - ошибка 400."""
    hero = get_hero_by_name(hero_name, db)
    if not hero.is_alive():
        logger.error(f"Попытка использовать мертвого героя: {hero_name}")
        raise HTTPException(status_code=400, detail="Герой мертв и не может сражаться!")
    return hero


def get_current_enemy(hero_name: str) -> Enemy:
    """Получить текущего врага героя из памяти программы. Если бой еще не начат - ошибка 404.

    Примечание: Враги по-прежнему хранятся в памяти (словарь database), а не в SQL базе.
    """
    enemy = database.get(hero_name + "_enemy")
    if not enemy:
        logger.error(f"Попытка выполнить действие вне боя: {hero_name}")
        raise HTTPException(status_code=404, detail="Бой не начат")
    return enemy


def get_hero_and_enemy(hero_name: str) -> tuple[Hero, Enemy]:
    """Получить героя и его текущего врага.

    Примечание: Данная функция не используется в текущей версии API,
    так как зависимости обрабатываются отдельно через Depends().
    """
    # Для совместимости оставляем, но в текущей реализации не используется
    pass  # Закомментировано, так как не используется


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserDB:

    credentials_exception = HTTPException(
        status_code=401,
        detail="Не удалось подтвердить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(UserDB).filter(UserDB.username == username).first()
    if user is None:
        raise credentials_exception
    return user


@app.post("/auth/register", response_model=Token)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = (
        db.query(UserDB).filter(UserDB.username == user_data.username).first()
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Имя пользователя уже занято")

    hashed_password = get_password_hash(user_data.password)

    new_user = UserDB(username=user_data.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()

    access_token = create_access_token(data={"sub": new_user.username})

    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/auth/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == user_data.username).first()
    if not user:
        raise HTTPException(
            status_code=401, detail="Неверное имя пользователя или пароль"
        )
    if not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401, detail="Неверное имя пользователя или пароль"
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/auth/login2")
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = db.query(UserDB).filter(UserDB.username == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=401, detail="Неверное имя пользователя или пароль"
        )
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401, detail="Неверное имя пользователя или пароль"
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/hero/create", response_model=GameState)
def create_hero(
    request: CreateHeroRequest,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Создание нового персонажа с сохранением в SQL базу данных."""
    # Проверяем, существует ли уже персонаж с таким именем в SQL базе
    existing = db.query(HeroDB).filter(HeroDB.name == request.name).first()
    if existing:
        logger.error(f"Попытка создать существующего героя: {request.name}")
        raise HTTPException(status_code=400, detail="Данный персонаж уже создан")

    # Создаем героя и сохраняем в SQL базу данных (вместо словаря database)
    hero = Hero(request.name)

    hero_db = HeroDB(
        name=hero.name,
        hp=hero.hp,
        max_hp=hero.max_hp,
        atk=hero.atk,
        defense=hero.defense,
        gold=hero.gold,
        potions=hero.potions,
        level=hero.level,
        exp=hero.exp,
        exp_to_next=hero.exp_to_next,
    )
    db.add(hero_db)
    db.commit()
    logger.info(f"Пользователь {current_user.username} создал героя {request.name}")

    return GameState(
        hero_name=hero.name,
        hero_hp=hero.hp,
        hero_max_hp=hero.max_hp,
        message="Вы успешно создали персонажа",
    )


@app.get("/hero/{hero_name}")
def get_hero_by_path(
    hero: Hero = Depends(get_hero_by_name),
    current_user: UserDB = Depends(get_current_user),
):
    """Получение полной информации о персонаже через path-параметр."""
    return {
        "name": hero.name,
        "hp": hero.hp,
        "max_hp": hero.max_hp,
        "level": hero.level,
        "gold": hero.gold,
        "exp": hero.exp,
        "exp_to_next": hero.exp_to_next,
        "hero_potions": hero.potions,
        "hero_isalive": hero.is_alive(),
    }


@app.get("/hero/stats")
def get_stats(
    hero: Hero = Depends(get_hero_by_name),
    current_user: UserDB = Depends(get_current_user),
):
    """Получение статистики персонажа по имени.
    Возвращает основную информацию: имя, текущее и максимальное здоровье, золото.
    """
    return HeroStats(
        name=hero.name,
        hp=hero.hp,
        max_hp=hero.max_hp,
        gold=hero.gold,
    )


@app.get("/hero")
def get_hero_by_query(
    hero: Hero = Depends(get_hero_by_name),
    current_user: UserDB = Depends(get_current_user),
):
    """Получение полной информации о персонаже через query-параметр."""
    return {
        "name": hero.name,
        "hp": hero.hp,
        "max_hp": hero.max_hp,
        "level": hero.level,
        "gold": hero.gold,
        "exp": hero.exp,
        "exp_to_next": hero.exp_to_next,
        "hero_potions": hero.potions,
        "hero_isalive": hero.is_alive(),
    }

@app.get("/heroes")
def get_all_heroes(db: Session = Depends(get_db)):
    cached = get_cache("heroes_list")
    if cached is not None:
        return cached

    heroes = db.query(HeroDB).all()
    result = [
        {
            "id": h.id,
            "name": h.name,
            "hp": h.hp,
            "max_hp": h.max_hp,
            "atk": h.atk,
            "defense": h.defense,
            "gold": h.gold,
            "potions": h.potions,
            "level": h.level,
            "exp": h.exp,
            "exp_to_next": h.exp_to_next,
            "description": h.description,
        }
        for h in heroes
    ]
    set_cache("heroes_list", result, ttl=300)
    return result

@app.post("/battle/start")
def start_battle(
    request: CreateHeroRequest,
    db: Session = Depends(get_db),
    hero: Hero = Depends(get_alive_hero),
    current_user: UserDB = Depends(get_current_user),
):
    """Начало сражения для указанного персонажа."""
    # Генерируем врага и сохраняем в памяти программы (враги не в SQL базе)
    enemy = generate_enemy()
    database[hero.name + "_enemy"] = enemy  # Используем hero.name вместо request.name

    return GameState(
        hero_name=hero.name,
        hero_hp=hero.hp,
        hero_max_hp=hero.max_hp,
        enemy_name=enemy.name,
        enemy_hp=enemy.hp,
        message=f"Вы встретили врага {enemy.name}! (HP: {enemy.hp})",
    )


@app.post("/battle/action", response_model=GameState)
def battle_action(
    request: ActionHeroRequest,
    background_tasks: BackgroundTasks,
    hero: Hero = Depends(get_alive_hero),
    enemy: Enemy = Depends(get_current_enemy),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Выполнение действия в бою (атака, зелье, побег)."""
    # Действие: Атака
    if request.action in ["attack", "атака", "Атака"]:
        hero_dmg = hero.attack()
        enemy.take_damage(hero_dmg)
        msg = f"Вы нанесли {hero_dmg} урона!"
        # Логируем атаку игрока.
        background_tasks.add_task(
            write_battle_log, hero.name, "attack", "hit", enemy.name
        )

        if enemy.is_alive():
            enemy_dmg = enemy.attack()
            hero.take_damage(enemy_dmg)
            msg += f"Враг нанес вам {enemy_dmg} урона!"

        if not enemy.is_alive():
            hero.gold += enemy.gold_reward
            hero.exp += enemy.exp_reward  # Добавляем опыт за победу

            # Проверяем, достаточно ли опыта для повышения уровня
            level_up_message = ""
            while hero.exp >= hero.exp_to_next:
                # Повышаем уровень героя
                hero.level += 1
                hero.exp -= hero.exp_to_next
                hero.exp_to_next = int(
                    hero.exp_to_next * 1.5
                )  # Увеличиваем требование к следующему уровню
                hero.max_hp += 10  # Увеличиваем максимальное здоровье
                hero.hp = (
                    hero.max_hp
                )  # Полностью восстанавливаем здоровье при повышении уровня
                hero.atk += 2  # Увеличиваем атаку
                hero.defense += 1  # Увеличиваем защиту
                level_up_message = f" Уровень повышен! Теперь вы {hero.level} уровня!"
                # Логируем повышение уровня
                background_tasks.add_task(
                    write_battle_log,
                    hero.name,
                    "level_up",
                    f"reached level {hero.level}",
                )
            # Сохраняем изменения героя в SQL базе данных
            hero_db = db.query(HeroDB).filter(HeroDB.name == hero.name).first()
            if hero_db:
                hero_db.hp = hero.hp
                hero_db.max_hp = hero.max_hp
                hero_db.gold = hero.gold
                hero_db.potions = hero.potions
                hero_db.level = hero.level
                hero_db.exp = hero.exp
                hero_db.exp_to_next = hero.exp_to_next
                hero_db.atk = hero.atk
                hero_db.defense = hero.defense
                db.commit()
            # Логируем победу в бою
            background_tasks.add_task(
                write_battle_log, hero.name, "attack", "victory", enemy.name
            )
            del database[hero.name + "_enemy"]
            msg += f"Враг {enemy.name} побежден! Вы получили {enemy.gold_reward} золота!{level_up_message}"
            return GameState(
                hero_name=hero.name,
                hero_hp=hero.hp,
                hero_max_hp=hero.max_hp,
                message=msg,
            )

    # Действие: Зелье
    elif request.action in ["potion", "зелье", "Зелье"]:
        if hero.potions > 0 and hero.hp < hero.max_hp:
            hero.potions -= 1
            hero.heal(HEAL_AMOUNT)
            # Сохраняем изменения в SQL базе данных
            hero_db = db.query(HeroDB).filter(HeroDB.name == hero.name).first()
            if hero_db:
                hero_db.potions = hero.potions
                hero_db.hp = hero.hp
                db.commit()
            # Логируем использование зелья
            background_tasks.add_task(
                write_battle_log,
                hero.name,
                "potion",
                f"healed to {hero.hp} hp",
                enemy.name,
            )
            msg = f"Вы использовали зелье! ({hero.hp} / {hero.max_hp})"
        else:
            logger.error(f"Попытка использовать зелье")
            raise HTTPException(status_code=400, detail="Нельзя использовать зелье")

        if enemy.is_alive():
            enemy_dmg = enemy.attack()
            hero.take_damage(enemy_dmg)
            msg += f"Враг нанес вам {enemy_dmg} урона!"

    # Действие: Побег
    elif request.action in ["flee", "побег", "Побег"]:
        if random.random() < 0.5:
            # Логируем успешный побег
            background_tasks.add_task(
                write_battle_log, hero.name, "flee", "success", enemy.name
            )
            del database[hero.name + "_enemy"]
            return GameState(
                hero_name=hero.name,
                hero_hp=hero.hp,
                hero_max_hp=hero.max_hp,
                message="Вы успешно сбежали!",
            )
        else:
            # Логируем неудачный побег
            background_tasks.add_task(
                write_battle_log, hero.name, "flee", "failed", enemy.name
            )
            msg = "Побег не удался!"
            enemy_dmg = enemy.attack()
            hero.take_damage(enemy_dmg)
            msg += f"Враг нанес вам {enemy_dmg} урона!"

    # Неизвестное действие
    else:
        raise HTTPException(status_code=400, detail="Неизвестное действие!")

    # Проверка: жив ли игрок
    if not hero.is_alive():
        # Логируем смерть героя
        background_tasks.add_task(
            write_battle_log, hero.name, "death", f"killed by {enemy.name}"
        )
        del database[hero.name + "_enemy"]
        return GameState(
            hero_name=hero.name,
            hero_hp=hero.hp,
            hero_max_hp=hero.max_hp,
            message=msg + " Вы трагически погибли...",
        )

    # Битва продолжается
    return GameState(
        hero_name=hero.name,
        hero_hp=hero.hp,
        hero_max_hp=hero.max_hp,
        enemy_name=enemy.name,
        enemy_hp=enemy.hp,
        message=msg,
    )
