from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supplier_data_cache = {}

def read_file(upload_file: UploadFile):
    contents = upload_file.file.read()
    upload_file.file.seek(0)
    if upload_file.filename.endswith('.csv'):
        return pd.read_csv(io.BytesIO(contents))
    else:
        return pd.read_excel(io.BytesIO(contents))

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(None)
):
    try:
        weekly_df = read_file(weekly_file)
        monthly_df = read_file(monthly_file)

        if 'Item Name' not in weekly_df.columns or 'Quantity' not in weekly_df.columns:
            return JSONResponse(content={"error": "Weekly file missing 'Item Name' or 'Quantity' column"}, status_code=400)
        if 'Item Name' not in monthly_df.columns or 'Quantity' not in monthly_df.columns:
            return JSONResponse(content={"error": "Monthly file missing 'Item Name' or 'Quantity' column"}, status_code=400)

        weekly_avg = weekly_df.groupby('Item Name')['Quantity'].sum() / 7
        monthly_avg = monthly_df.groupby('Item Name')['Quantity'].sum() / 30

        suggested_par = pd.concat([weekly_avg, monthly_avg], axis=1)
        suggested_par.columns = ['weekly', 'monthly']
        suggested_par['Suggested Par'] = suggested_par.max(axis=1)

        supplier_name = "Unknown"
        supplier_df = None
        if supplier_file:
            supplier_df = read_file(supplier_file)
            supplier_name = supplier_file.filename.split()[0] if " " in supplier_file.filename else supplier_file.filename.split(".")[0]
            supplier_data_cache[supplier_name.lower()] = supplier_df

        results = []
        for item, row in suggested_par.iterrows():
            matched_supplier = "Unknown"
            expected_delivery = 0
            supplier_unit = ""
            item_upper = str(item).upper()

            if supplier_df is not None:
                for index, srow in supplier_df.iterrows():
                    s_item = str(srow.get("Item Name", "")).upper()
                    if s_item in item_upper or item_upper in s_item:
                        matched_supplier = supplier_name
                        expected_delivery = srow.get("Quantity", 0)
                        supplier_unit = str(srow.get("Unit", "")).upper()
                        break

            results.append({
                "Item": item,
                "Item Code": "",
                "Unit": str(weekly_df[weekly_df['Item Name'] == item]['Unit'].values[0]) if 'Unit' in weekly_df.columns and item in weekly_df['Item Name'].values else "",
                "Suggested Par": round(row['Suggested Par'], 2),
                "Stock in Hand": 0,
                "Expected Delivery": expected_delivery,
                "Final Stock Needed": round(row['Suggested Par'], 2),  # Basic logic only, will adjust with stock/delivery
                "Supplier": matched_supplier
            })

        return {"data": results}

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)