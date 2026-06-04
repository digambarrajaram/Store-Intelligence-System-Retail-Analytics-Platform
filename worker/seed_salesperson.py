"""
Seed mock salesperson transaction data into Redis so GET /api/v1/insights/salesperson returns data.

Writes to Redis key schema: pos:store:{store_id}:{date} (hash of order_id -> JSON transaction)
Queried by: TransactionImporter.get_salesperson_ranking() in services/transaction_importer.py

Run: docker compose exec <worker_container> python /app/worker/seed_salesperson.py
Or:  docker compose exec api python /app/worker/seed_salesperson.py
"""
import os
import json
import redis as redis_client

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
STORE_ID = os.getenv("STORE_ID", "store_1")
DATE = os.getenv("SALESPERSON_DATE", "2026-06-04")

r = redis_client.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

SALESPEOPLE = [
    {"name": "Alice Chen",   "orders": 12, "gmv": 4500.00},
    {"name": "Bob Martinez", "orders": 9,  "gmv": 3200.50},
    {"name": "Carol Smith",  "orders": 15, "gmv": 6100.75},
    {"name": "Dave Johnson", "orders": 7,  "gmv": 2100.00},
    {"name": "Eve Williams", "orders": 11, "gmv": 3900.25},
]

key = f"pos:store:{STORE_ID}:{DATE}"
r.delete(key)

order_id = 1000
for sp in SALESPEOPLE:
    for _ in range(sp["orders"]):
        order_id += 1
        gmv = round(sp["gmv"] / sp["orders"], 2)
        transaction = {
            "order_id": str(order_id),
            "order_date": DATE,
            "salesperson_name": sp["name"],
            "qty": 2,
            "GMV": gmv,
            "NMV": round(gmv * 0.9, 2),
            "sub_category": "Apparel",
            "brand_name": "GenericBrand",
            "dep_name": "Fashion"
        }
        r.hset(key, str(order_id), json.dumps(transaction))

r.expire(key, 86400)
print(f"Seeded {order_id - 1000} transactions for {len(SALESPEOPLE)} salespeople into Redis key '{key}'")
