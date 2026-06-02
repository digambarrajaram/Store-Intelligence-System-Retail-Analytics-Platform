import json
import os
from fastapi import APIRouter, HTTPException, Query, Depends
from redis import Redis
from datetime import datetime

from services.transaction_importer import TransactionImporter

router = APIRouter()

def get_redis():
    return Redis(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0,
        decode_responses=True
    )

@router.get("/insights/correlation")
async def get_correlation_insights(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    r: Redis = Depends(get_redis)
):
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")

    # Get vision footfall
    footfall = int(r.get(f"vision:footfall:{date}") or 0)

    # Get POS aggregates
    agg_data = r.hgetall(f"pos:aggregates:{date}")
    if not agg_data:
        raise HTTPException(status_code=404, detail=f"No POS data found for date {date}")

    transactions = int(agg_data.get("total_orders", 0))
    total_gmv = float(agg_data.get("total_gmv", 0))
    avg_basket_gmv = total_gmv / transactions if transactions > 0 else 0.0
    conversion_rate_pct = (transactions / footfall * 100) if footfall > 0 else 0.0
    revenue_per_visitor = total_gmv / footfall if footfall > 0 else 0.0
    top_categories = json.loads(agg_data.get("top_categories", "[]"))
    top_performing_category = top_categories[0] if top_categories else ""

    if conversion_rate_pct > 30:
        insight = f"Conversion rate is {conversion_rate_pct:.2f}% — exceeds the 30% target."
    elif conversion_rate_pct > 20:
        insight = f"Conversion rate is {conversion_rate_pct:.2f}% — above average but below the 30% target."
    else:
        insight = f"Conversion rate is {conversion_rate_pct:.2f}% — below target; review footfall quality or sales strategy."

    return {
        "date": date,
        "footfall": footfall,
        "transactions": transactions,
        "conversion_rate_pct": round(conversion_rate_pct, 2),
        "revenue_per_visitor": round(revenue_per_visitor, 2),
        "avg_basket_gmv": round(avg_basket_gmv, 2),
        "top_performing_category": top_performing_category,
        "insight": insight
    }


@router.get("/insights/salesperson")
async def get_salesperson_leaderboard(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    r: Redis = Depends(get_redis)
):
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")

    ranking = TransactionImporter().get_salesperson_ranking(r, date)
    return ranking or []