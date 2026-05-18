import random
import logging

# Настройка логирования для игрового движка
logger = logging.getLogger(__name__)

# Константы баланса для героя
HERO_BASE_HP = 50
HERO_BASE_ATK = 8
HERO_BASE_DEFENSE = 2
HERO_START_GOLD = 20
HERO_START_POTIONS = 2
HERO_START_EXP_TO_NEXT = 10
CRIT_CHANCE = 0.2  # Шанс критического удара
CRIT_MULTIPLIER = 2  # Множитель урона при критическом ударе


class Hero:
    """Класс героя игрока.
    
    Содержит все характеристики персонажа и методы для взаимодействия в бою.
    """
    
    def __init__(self, name):
        self.name = name
        self.hp = HERO_BASE_HP
        self.max_hp = HERO_BASE_HP
        self.atk = HERO_BASE_ATK
        self.defense = HERO_BASE_DEFENSE
        self.gold = HERO_START_GOLD
        self.potions = HERO_START_POTIONS
        self.inventory = []
        self.level = 1
        self.exp = 0
        self.exp_to_next = HERO_START_EXP_TO_NEXT

    def attack(self):
        """Выполняет атаку героя с возможностью критического удара.
        
        Returns:
            int: Нанесенный урон (обычный или критический).
        """
        base_dmg = self.atk + random.randint(-2, 3)
        if random.random() < CRIT_CHANCE:
            crit_dmg = base_dmg * CRIT_MULTIPLIER
            logger.info(f"Критический удар! Урон: {crit_dmg}")
            return crit_dmg
        return base_dmg

    def take_damage(self, dmg):
        """Получение урона с учетом защиты героя.
        
        Args:
            dmg: Базовый урон от атаки противника.
            
        Returns:
            int: Фактический полученный урон (после вычитания защиты).
        """
        actual_damage = max(0, dmg - self.defense)
        self.hp -= actual_damage
        return actual_damage

    def heal(self, amount):
        """Восстановление здоровья.
        
        Args:
            amount: Количество восстанавливаемого здоровья.
            
        Returns:
            int: Текущее здоровье после лечения.
        """
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp

    def is_alive(self):
        """Проверка жизнеспособности героя.
        
        Returns:
            bool: True если герой жив (hp > 0), иначе False.
        """
        return self.hp > 0


class Enemy:
    """Класс врага (монстра).
    
    Представляет противника с базовыми характеристиками и наградой за победу.
    """
    
    def __init__(self, name, hp, atk, gold_reward, exp_reward):
        self.name = name
        self.hp = hp
        self.max_hp = hp
        self.atk = atk
        self.gold_reward = gold_reward
        self.exp_reward = exp_reward

    def attack(self):
        """Атака врага с небольшим разбросом урона.
        
        Returns:
            int: Нанесенный урон.
        """
        return self.atk + random.randint(-1, 3)

    def take_damage(self, dmg):
        """Получение урона врагом.
        
        Args:
            dmg: Нанесенный урон.
            
        Returns:
            int: Полученный урон (возвращается для логирования).
        """
        self.hp -= dmg
        return dmg

    def is_alive(self):
        """Проверка жизнеспособности врага.
        
        Returns:
            bool: True если враг жив (hp > 0), иначе False.
        """
        return self.hp > 0
