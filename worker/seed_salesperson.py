"""
Seed mock salesperson transaction data into Redis so GET /api/v1/insights/salesperson returns data.

Also seeds conversion funnel data so conversion rate and funnel charts work.

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
order_ids = []
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
        order_ids.append(str(order_id))

r.expire(key, 86400)
print(f"Seeded {order_id - 1000} transactions for {len(SALESPEOPLE)} salespeople into Redis key '{key}'")

# Also seed POS aggregates for the insights/correlation endpoint
agg_key = f"pos:store:{STORE_ID}:aggregates:{DATE}"
total_orders = order_id - 1000
total_gmv = sum(sp["gmv"] for sp in SALESPEOPLE)
total_nmv = sum(round(sp["gmv"] * 0.9, 2) * sp["orders"] for sp in SALESPEOPLE)
r.hset(agg_key, mapping={
    "total_orders": total_orders,
    "total_gmv": total_gmv,
    "total_nmv": total_nmv,
    "avg_basket_size": 2.0,
    "top_categories": json.dumps(["Apparel", "Electronics", "Home"]),
    "top_brands": json.dumps(["GenericBrand", "BrandX", "BrandY"])
})
r.expire(agg_key, 86400)
print(f"Seeded POS aggregates into Redis key '{agg_key}'")

# Seed conversion funnel data so conversion rate and funnel charts work
# The funnel endpoint reads from funnel:store:{store_id}:entered_store etc.
# The ConversionEngine writes session IDs to these sets.
# We seed some mock session IDs to make the funnel non-empty.
import time
funnel_prefix = f"funnel:store:{STORE_ID}"

# Seed entered_store with some session IDs
entered_ids = [f"seed_session_{i}" for i in range(1, 51)]  # 50 entered
browsed_ids = [f"seed_session_{i}" for i in range(1, 36)]   # 35 browsed
checkout_ids = [f"seed_session_{i}" for i in range(1, 21)]  # 20 reached checkout
converted_ids = order_ids[:15]  # 15 converted (use actual order IDs)

r.sadd(f"{funnel_prefix}:entered_store", *entered_ids)
r.sadd(f"{funnel_prefix}:browsed_gt_2min", *browsed_ids)
r.sadd(f"{funnel_prefix}:reached_checkout_zone", *checkout_ids)
r.sadd(f"{funnel_prefix}:converted", *converted_ids)

# Also seed per-camera funnel data for camera_1 through camera_4
for cam_num in range(1, 5):
    cam_prefix = f"{funnel_prefix}:camera:camera_{cam_num}"
    # Distribute sessions across cameras
    cam_entered = [s for s in entered_ids if hash(s) % 4 == cam_num - 1]
    cam_browsed = [s for s in browsed_ids if hash(s) % 4 == cam_num - 1]
    cam_checkout = [s for s in checkout_ids if hash(s) % 4 == cam_num - 1]
    if cam_entered:
        r.sadd(f"{cam_prefix}:entered_store", *cam_entered)
    if cam_browsed:
        r.sadd(f"{cam_prefix}:browsed_gt_2min", *cam_browsed)
    if cam_checkout:
        r.sadd(f"{cam_prefix}:reached_checkout_zone", *cam_checkout)

print(f"Seeded funnel data: {len(entered_ids)} entered, {len(browsed_ids)} browsed, {len(checkout_ids)} checkout, {len(converted_ids)} converted")
print("Seed complete.")
