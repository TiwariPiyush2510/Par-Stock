# === main.py ===
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate")
async def calculate_par_stock(weekly_file: UploadFile = File(...), monthly_file: UploadFile = File(...)):
    weekly_data = pd.read_excel(BytesIO(await weekly_file.read()))
    monthly_data = pd.read_excel(BytesIO(await monthly_file.read()))

    # Group and sum by Item Code for both
    weekly_grouped = weekly_data.groupby("Item Code").agg({
        "Item": "first",
        "Unit": "first",
        "Quantity": "sum"
    }).reset_index()
    monthly_grouped = monthly_data.groupby("Item Code").agg({
        "Item": "first",
        "Unit": "first",
        "Quantity": "sum"
    }).reset_index()

    result = []
    all_codes = set(weekly_grouped["Item Code"]).union(set(monthly_grouped["Item Code"]))

    for code in all_codes:
        weekly_row = weekly_grouped[weekly_grouped["Item Code"] == code]
        monthly_row = monthly_grouped[monthly_grouped["Item Code"] == code]

        item_name = weekly_row["Item"].values[0] if not weekly_row.empty else monthly_row["Item"].values[0]
        unit = weekly_row["Unit"].values[0] if not weekly_row.empty else monthly_row["Unit"].values[0]

        weekly_qty = weekly_row["Quantity"].values[0] if not weekly_row.empty else 0
        monthly_qty = monthly_row["Quantity"].values[0] if not monthly_row.empty else 0

        weekly_avg = weekly_qty / 7 if weekly_qty else 0
        monthly_avg = monthly_qty / 30 if monthly_qty else 0

        suggested_par = max(weekly_avg, monthly_avg)

        result.append({
            "Item": item_name,
            "Item Code": code,
            "Unit": unit,
            "Suggested Par": round(suggested_par, 2)
        })

    return {"result": result}