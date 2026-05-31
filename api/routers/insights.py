import pandas as pd
import redis
import json
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime

router = APIRouter()
# Initialize Redis client
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def get_footfall_from_vision(date: str) -> int:
    """
    Retrieve vision footfall data for a given date.
    In a real system, this would query a vision system database or service.
    For this implementation, we retrieve from Redis key 'vision:footfall:{date}'.
    """
    key = f"vision:footfall:{date}"
    footfall = r.get(key)
    if footfall is None:
        # If not found, return 0 or raise? We'll return 0 and let conversion rate be 0.
        return 0
    try:
        return int(footfall)
    except ValueError:
        return 0

@router.get("/insights/correlation")
async def get_correlation_insights(date: str = Query(..., description="Date in YYYY-MM-DD format")):
    """
    Merge vision footfall data with POS data to compute correlation insights.
    """
    try:
        # Validate date format
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")

        # Get vision footfall data
        footfall = get_footfall_from_vision(date)

        # Get POS aggregates for the date
        agg_key = f"pos:aggregates:{date}"
        agg_data = r.hgetall(agg_key)
        if not agg_data:
            raise HTTPException(status_code=404, detail=f"No POS data found for date {date}")

        # Extract metrics
        transactions = int(agg_data.get("total_orders", 0))
        total_gmv = float(agg_data.get("total_gmv", 0))
        total_nmv = float(agg_data.get("total_nmv", 0))
        avg_basket_size = float(agg_data.get("avg_basket_size", 0))
        top_categories = json.loads(agg_data.get("top_categories", "[]"))
        top_brands = json.loads(agg_data.get("top_brands", "[]"))

        # Calculate derived metrics
        conversion_rate_pct = (transactions / footfall * 100) if footfall > 0 else 0.0
        revenue_per_visitor = total_gmv / footfall if footfall > 0 else 0.0
        avg_basket_gmv = total_gmv / transactions if transactions > 0 else 0.0
        top_performing_category = top_categories[0] if top_categories else ""

        # Generate insight
        insight = f"Conversion rate is {conversion_rate_pct:.2f}%. "
        if conversion_rate_pct > 30:
            insight += "This exceeds the target conversion rate of 30%."
        elif conversion_rate_pct > 20:
            insight += "This is above average but below the target of 30%."
        else:
            insight += "This is below the target conversion rate of 30%; consider investigating footfall quality or sales effectiveness."

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

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute correlation insights: {str(e)}")

@router.get("/insights/salesperson")
async def get_salesperson_leaderboard(date: str = Query(..., description="Date in YYYY-MM-DD format")):
    """
    Get ranked leaderboard of salespeople by total GMV.
    """
    try:
        # Validate date format
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")

        # Get all transactions for the date from Redis hash
        pos_key = f"pos:{date}"
        transactions_hash = r.hgetall(pos_key)
        if not transactions_hash:
            raise HTTPException(status_code=404, detail=f"No transaction data found for date {date}")

        # Convert hash values (JSON strings) to list of dicts
        transactions_list = []
        for value in transactions_hash.values():
            try:
                transactions_list.append(json.loads(value))
            except json.JSONDecodeError:
                continue  # Skip invalid entries

        if not transactions_list:
            raise HTTPException(status_code=404, detail=f"No valid transaction data found for date {date}")

        df = pd.DataFrame(transactions_list)

        # Group by salesperson
        grouped = df.groupby('salesperson_name').agg(
            order_count=('order_id', 'count'),
            total_gmv=('GMV', 'sum')
        ).reset_index()

        # Calculate average basket size (GMV per transaction)
        grouped['avg_basket'] = grouped['total_gmv'] / grouped['order_count']

        # Sort by total_gmv descending (leaderboard)
        grouped = grouped.sort_values('total_gmv', ascending=False)

        # Convert to list of dicts
        result = grouped.to_dict('records')

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate salesperson leaderboard: {str(e)}")