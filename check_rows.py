import asyncio, os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def check():
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")
    conn = await asyncpg.connect(url)

    total = await conn.fetchval("SELECT COUNT(*) FROM audit_log")
    print(f"Total rows in audit_log: {total}")

    by_type = await conn.fetch(
        "SELECT event_type, COUNT(*) AS n FROM audit_log GROUP BY event_type ORDER BY n DESC"
    )
    for row in by_type:
        print(f"  {row['event_type']}: {row['n']}")

    print("\nMost recent 5:")
    recent = await conn.fetch(
        "SELECT event_type, source, occurred_at, recorded_at "
        "FROM audit_log ORDER BY recorded_at DESC LIMIT 5"
    )
    for row in recent:
        lag_ms = (row['recorded_at'] - row['occurred_at']).total_seconds() * 1000
        print(f"  {row['recorded_at']} | {row['event_type']} | lag: {lag_ms:.0f}ms")
    await conn.close()

asyncio.run(check())