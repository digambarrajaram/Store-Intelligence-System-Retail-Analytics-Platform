import json
import os
from fastapi import APIRouter, Request, UploadFile, HTTPException, Query
from redis import Redis

from services.transaction_importer import TransactionImporter

router = APIRouter()

@router.post("/pos/ingest")
async def ingest_pos_data(
    request: Request,
    store_id: str = Query("store_1"),
):
    r = request.app.state.redis
    content_type = request.headers.get('content-type', '')

    importer = TransactionImporter(store_id=store_id)

    try:
        if content_type.startswith('multipart/form-data'):
            form = await request.form()
            file: UploadFile = form.get('file')
            if not file:
                raise HTTPException(status_code=400, detail="No file uploaded")
            contents = await file.read()
            df = importer.parse_csv(contents)
        elif content_type == 'application/json':
            body = await request.body()
            data = json.loads(body)
            df = importer.parse_json(data)
        else:
            raise HTTPException(status_code=400, detail="Use multipart/form-data or application/json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = await importer.store_transactions(df, r)
    persisted_dates = list(result.get('aggregates', {}).keys())

    response = {
        "store_id": store_id,
        "status": "success",
        "dates": persisted_dates,
        "transactions_processed": result.get('transactions_processed', 0),
        "salesperson_ranking": result.get('salesperson_ranking', {}),
        "aggregates_cached": True
    }

    if len(persisted_dates) == 1:
        response["date"] = persisted_dates[0]

    return response
