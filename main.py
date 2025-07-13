from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
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

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    def read_file(file):
        if file.filename.endswith(".csv"):
            return pd.read_csv(io.BytesIO(await file.read()))
        else:
            return pd.read_excel(io.BytesIO(await file.read()))

    weekly_df = await read_file(weekly_file)
    monthly_df = await read_file(monthly_file)
    supplier_df = await read_file(supplier_file)

    consumption_df = pd.concat([weekly_df, monthly_df])
    consumption_df["Daily Avg"] = consumption_df["Qty"] / consumption_df["Days"]
    avg_df = consumption_df.groupby("Item Name")["Daily Avg"].max().reset_index()

    supplier_df["Item Name"] = supplier_df["Item Name"].str.strip().str.upper()
    avg_df["Item Name"] = avg_df["Item Name"].str.strip().str.upper()

    merged = pd.merge(avg_df, supplier_df, left_on="Item Name", right_on="Item Name", how="inner")

    result = []
    for _, row in merged.iterrows():
        result.append({
            "Item": row["Item Name"],
            "Item Code": row.get("Item Code", ""),
            "Unit": row.get("Unit", ""),
            "Suggested Par": round(row["Daily Avg"], 2),
            "Stock in Hand": 0,
            "Expected Delivery": 0,
            "Final Stock Needed": 0,
            "Supplier": row.get("Supplier", "")
        })
    return result