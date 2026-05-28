import json
import os
from typing import Optional, Any
import redis


REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses = True)

def check_redis():
    try:
        redis_client.ping()
        print("Redis connected")
    except redis.ConnectionError:
        print("Redis not avaliable")

def set_cache(key: str, value: Any, ttl: int = 300) -> None:
    try:
        json_value = json.dumps(value, ensure_ascii=False)
        redis_client.setex(key, ttl, json_value)
    except redis.RedisError as e:
        print(f"Redis set_cache error {e}")

def get_cache(key: str) -> Optional[Any]:
    try:
        cached = redis_client.get(key)
        if cached is None:
            return None
        return json.loads(cached)
    except (redis.RedisError, json.JSONDecodeError) as e:
        print(f"Redis get_cache error {e}")

def delete_cache(key: str) -> None:
    try:
        redis_client.delete(key)
    except redis.RedisError as e:
        print(f"Redis delete_cache error {e}")

