from datetime import datetime, timezone

from fastapi import HTTPException

from utils.mock_llm import MOCK_RESPONSES
from .config import settings
from .redis_client import r

# Integer nanodollars avoid rounding tiny charges. The mock estimates two tokens per word.
INPUT_PRICE = 150
OUTPUT_PRICE = 600
MAX_OUTPUT_TOKENS = max(2 * len(answer.split())
                        for answers in MOCK_RESPONSES.values() for answer in answers)

reserve = r.register_script("""
local spent = tonumber(redis.call('GET', KEYS[1]) or '0')
if spent + tonumber(ARGV[1]) > tonumber(ARGV[2]) then return 0 end
redis.call('INCRBY', KEYS[1], ARGV[1])
redis.call('EXPIRE', KEYS[1], 172800)
return 1
""")


def answer_with_budget(question: str, generate) -> str:
    day = datetime.now(timezone.utc).date()
    key = f"agent:budget:{day}"
    input_cost = 2 * len(question.split()) * INPUT_PRICE
    reserved = input_cost + MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    limit = int(settings.daily_budget_usd * 10**9)
    if not reserve(keys=[key], args=[reserved, limit]):
        raise HTTPException(402, "Insufficient daily budget")

    try:
        answer = generate(question)
    except Exception:
        r.decrby(key, reserved)
        raise
    actual = input_cost + 2 * len(answer.split()) * OUTPUT_PRICE
    r.decrby(key, reserved - actual)
    return answer
