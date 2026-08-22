"""
Duplicate check for Phase 1 exit criterion:
"Zero duplicate events observed downstream during a sustained test window."

Dedup keys per Backend Schema v2.0:
  trade        -> (exchange, symbol, trade_id)
  depth_update -> (exchange, symbol, final_update_id)
  ticker       -> no key required (latest value wins)
"""
import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def check():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))

    total = await conn.fetchval("SELECT COUNT(*) FROM audit_log")
    print(f"Total rows: {total}\n")

    # --- Duplicate trades ---
    dup_trades = await conn.fetch("""
        SELECT payload->>'exchange' AS exchange,
               payload->>'symbol'   AS symbol,
               payload->>'trade_id' AS trade_id,
               COUNT(*) AS n
        FROM audit_log
        WHERE event_type = 'trade'
        GROUP BY 1, 2, 3
        HAVING COUNT(*) > 1
        ORDER BY n DESC
        LIMIT 10
    """)
    print(f"Duplicate trades: {len(dup_trades)}")
    for r in dup_trades:
        print(f"   {r['symbol']} trade_id={r['trade_id']} seen {r['n']}x")

    # --- Duplicate depth updates ---
    dup_depth = await conn.fetch("""
        SELECT payload->>'symbol'          AS symbol,
               payload->>'final_update_id' AS final_update_id,
               COUNT(*) AS n
        FROM audit_log
        WHERE event_type = 'depth_update'
        GROUP BY 1, 2
        HAVING COUNT(*) > 1
        ORDER BY n DESC
        LIMIT 10
    """)
    print(f"\nDuplicate depth updates: {len(dup_depth)}")
    for r in dup_depth:
        print(f"   {r['symbol']} final_update_id={r['final_update_id']} seen {r['n']}x")

    # --- Sequence gaps in the order book ---
    # Contiguity is enforced in-memory by OrderBook.apply(), but a gap in
    # what was PERSISTED would mean events were dropped between the book
    # and the DB. Expect gaps only across the reconnect boundary.
    rows = await conn.fetch("""
        SELECT (payload->>'first_update_id')::bigint AS first_id,
               (payload->>'final_update_id')::bigint AS final_id
        FROM audit_log
        WHERE event_type = 'depth_update'
        ORDER BY (payload->>'final_update_id')::bigint
    """)
    gaps = []
    for prev, curr in zip(rows, rows[1:]):
        if curr["first_id"] != prev["final_id"] + 1:
            gaps.append((prev["final_id"], curr["first_id"]))

    print(f"\nSequence gaps in persisted depth updates: {len(gaps)}")
    for a, b in gaps[:10]:
        print(f"   gap: {a} -> {b}  (missing {b - a - 1} update ids)")

    print("\n--- VERDICT ---")
    if not dup_trades and not dup_depth:
        print("PASS: zero duplicates")
    else:
        print("FAIL: duplicates found")

    await conn.close()


asyncio.run(check())