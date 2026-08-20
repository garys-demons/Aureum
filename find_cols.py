import asyncio, os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def check():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    cols = await conn.fetch(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'audit_log' ORDER BY ordinal_position"
    )
    for c in cols:
        print(f"  {c['column_name']}: {c['data_type']}")
    await conn.close()

asyncio.run(check())