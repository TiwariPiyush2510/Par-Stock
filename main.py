from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supplier_data_cache = {}

def read_file(upload_file: UploadFile):
    filename = upload_file.filename.lower()
    content = upload_file.file.read()
    upload_file.file.seek(0)

    if filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
    else:
        df = pd.read_excel(io.BytesIO(content))
    return df

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(None)
):
    try:
        weekly_df = read_file(weekly_file)
        monthly_df = read_file(monthly_file)
        supplier_df = None
        supplier_name = "Unknown"

        if supplier_file:
            supplier_df = read_file(supplier_file)
            filename_lower = supplier_file.filename.lower()

            supplier_map = {
                "barakat": "Barakat",
                "ofi": "OFI",
                "al ahlia": "Al Ahlia",
                "emirates": "Emirates",
                "harvey": "Harvey"
            }

            for key, name in supplier_map.items():
                if key in filename_lower:
                    supplier_name = name
                    break

            supplier_data_cache[supplier_name] = supplier_df

        # Merge weekly and monthly data on Item
        weekly_df = weekly_df.rename(columns=lambda x: x.strip())
        monthly_df = monthly_df.rename(columns=lambda x: x.strip())
        merged_df = pd.merge(weekly_df, monthly_df, on="Item", suffixes=("_weekly", "_monthly"))

        results = []
        for _, row in merged_df.iterrows():
            item_name = str(row["Item"]).strip()
            item_code = row.get("Item Code", "")
            unit = row.get("Unit", "")
            weekly = float(row.get("Qty_weekly", 0))
            monthly = float(row.get("Qty_monthly", 0))

            daily_avg_weekly = weekly / 7
            daily_avg_monthly = monthly / 30
            suggested_par = max(daily_avg_weekly, daily_avg_monthly)

            supplier_match = "Unknown"
            for sup_name, sup_df in supplier_data_cache.items():
                sup_df.columns = sup_df.columns.str.strip()
                if "Item Name" in sup_df.columns:
                    match = sup_df[sup_df["Item Name"].str.strip().str.lower() == item_name.lower()]
                    if not match.empty:
                        supplier_match = sup_name
                        break

            results.append({
                "Item": item_name,
                "Item Code": item_code,
                "Unit": unit,
                "Suggested Par": round(suggested_par, 2),
                "Stock in Hand": 0,
                "Expected Delivery": 0,
                "Final Stock Needed": round(suggested_par, 2),
                "Supplier": supplier_match
            })

        return JSONResponse(content=results)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})