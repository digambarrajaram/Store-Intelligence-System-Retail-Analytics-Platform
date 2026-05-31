import pandas as pd
import redis
import json
import io
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from datetime import datetime

router = APIRouter()
# Initialize Redis client
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

@router.post("/pos/ingest")
async def ingest_pos_data(request: Request):
    """
    Ingest POS data via CSV file upload or JSON array.
    Stores transactions in Redis hash 'pos:YYYY-MM-DD' keyed by order_id.
    Computes and caches daily aggregates with 24h TTL.
    """
    try:
        content_type = request.headers.get('content-type')
        df = None

        if content_type.startswith('multipart/form-data'):
            # Handle file upload
            form = await request.form()
            file: UploadFile = form.get('file')
            if not file:
                raise HTTPException(status_code=400, detail="No file uploaded")
            contents = await file.read()
            df = pd.read_csv(io.BytesIO(contents))
        elif content_type == 'application/json':
            # Handle JSON array
            body = await request.body()
            data = json.loads(body)
            if not isinstance(data, list):
                raise HTTPException(status_code=400, detail="JSON payload must be an array of transactions")
            df = pd.DataFrame(data)
        else:
            raise HTTPException(status_code=400, detail="Unsupported content type. Use multipart/form-data or application/json")

        # Validate required columns
        required_columns = {'order_id', 'order_date', 'order_time', 'customer_number', 
                          'salesperson_name', 'qty', 'GMV', 'NMV', 'sub_category', 
                          'brand_name', 'dep_name'}
        if not required_columns.issubset(set(df.columns)):
            missing = required_columns - set(df.columns)
            raise HTTPException(status_code=400, detail=f"Missing columns: {missing}")

        # Extract date (assuming all records are for same date)
        order_date = df['order_date'].iloc[0]
        # Validate date format
        try:
            datetime.strptime(order_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")

        # Store transactions in Redis hash
        pos_key = f"pos:{order_date}"
        pipe = r.pipeline()
        for _, row in df.iterrows():
            field = row['order_id']
            value = row.to_json()
            pipe.hset(pos_key, field, value)
        pipe.expire(pos_key, 24 * 60 * 60)  # 24h TTL
        pipe.execute()

        # Compute daily aggregates
        total_orders = len(df)
        total_gmv = df['GMV'].sum()
        total_nmv = df['NMV'].sum()
        avg_basket_size = df['qty'].mean()

        # Top 3 categories by GMV
        top_categories = (
            df.groupby('sub_category')['GMV']
            .sum()
            .nlargest(3)
            .index.tolist()
        )

        # Top 3 brands by GMV
        top_brands = (
            df.groupby('brand_name')['GMV']
            .sum()
            .nlargest(3)
            .index.tolist()
        )

        # Store aggregates in Redis hash
        agg_key = f"pos:aggregates:{order_date}"
        agg_data = {
            "total_orders": total_orders,
            "total_gmv": total_gmv,
            "total_nmv": total_nmv,
            "avg_basket_size": avg_basket_size,
            "top_categories": json.dumps(top_categories),
            "top_brands": json.dumps(top_brands)
        }
        r.hset(agg_key, mapping=agg_data)
        r.expire(agg_key, 24 * 60 * 60)  # 24h TTL

        return {
            "status": "success",
            "date": order_date,
            "transactions_processed": total_orders,
            "aggregates_cached": True
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")