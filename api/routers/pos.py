import pandas as pd
import json
import io
import os
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Depends
from redis import Redis
from datetime import datetime

router = APIRouter()

def get_redis():
    return Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0,
        decode_responses=True
    )

@router.post("/pos/ingest")
async def ingest_pos_data(
    request: Request,
    r: Redis = Depends(get_redis)
):
    content_type = request.headers.get('content-type', '')

    if content_type.startswith('multipart/form-data'):
        form = await request.form()
        file: UploadFile = form.get('file')
        if not file:
            raise HTTPException(status_code=400, detail="No file uploaded")
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
    elif content_type == 'application/json':
        body = await request.body()
        data = json.loads(body)
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="JSON payload must be an array")
        df = pd.DataFrame(data)
    else:
        raise HTTPException(status_code=400, detail="Use multipart/form-data or application/json")

    required_columns = {'order_id', 'order_date', 'salesperson_name', 'qty', 'GMV', 'NMV', 'sub_category', 'brand_name', 'dep_name'}
    missing = required_columns - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {missing}")

    order_date = str(df['order_date'].iloc[0])
    try:
        datetime.strptime(order_date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format in data. Expected YYYY-MM-DD")

    # Store transactions
    pipe = r.pipeline()
    for _, row in df.iterrows():
        pipe.hset(f"pos:{order_date}", str(row['order_id']), row.to_json())
    pipe.expire(f"pos:{order_date}", 86400)

    # Compute aggregates
    total_orders = len(df)
    total_gmv = float(df['GMV'].sum())
    total_nmv = float(df['NMV'].sum())
    avg_basket_size = float(df['qty'].mean())
    top_categories = df.groupby('sub_category')['GMV'].sum().nlargest(3).index.tolist()
    top_brands = df.groupby('brand_name')['GMV'].sum().nlargest(3).index.tolist()

    pipe.hset(f"pos:aggregates:{order_date}", mapping={
        "total_orders": total_orders,
        "total_gmv": total_gmv,
        "total_nmv": total_nmv,
        "avg_basket_size": avg_basket_size,
        "top_categories": json.dumps(top_categories),
        "top_brands": json.dumps(top_brands)
    })
    pipe.expire(f"pos:aggregates:{order_date}", 86400)
    pipe.execute()

    return {
        "status": "success",
        "date": order_date,
        "transactions_processed": total_orders,
        "aggregates_cached": True
    }