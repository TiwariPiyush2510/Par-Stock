from fastapi import FastAPI, UploadFile, File
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
    # Load weekly and monthly reports
    weekly_data = pd.read_excel(BytesIO(await weekly_file.read()))
    monthly_data = pd.read_excel(BytesIO(await monthly_file.read()))

    # Group by Item Code and sum Quantity
    weekly_grouped = weekly_data.groupby("Item Code").agg({
        "Quantity": "sum",
        "Item Name": "first",
        "Unit": "first",
        "Category Name": "first"
    }).reset_index()
    weekly_grouped["Daily Avg Weekly"] = weekly_grouped["Quantity"] / 7

    monthly_grouped = monthly_data.groupby("Item Code").agg({
        "Quantity": "sum",
        "Item Name": "first",
        "Unit": "first",
        "Category Name": "first"
    }).reset_index()
    monthly_grouped["Daily Avg Monthly"] = monthly_grouped["Quantity"] / 30

    # Merge both reports
    combined = pd.merge(weekly_grouped, monthly_grouped, on="Item Code", how="outer", suffixes=("_weekly", "_monthly")).fillna(0)

    # Calculate Suggested Par = max(daily avg weekly, daily avg monthly)
    combined["Suggested Par"] = combined[["Daily Avg Weekly", "Daily Avg Monthly"]].max(axis=1)

    # Prepare response
    result = []
    for _, row in combined.iterrows():
        result.append({
            "Item": row["Item Name_weekly"] or row["Item Name_monthly"],
            "Item Code": row["Item Code"],
            "Unit": row["Unit_weekly"] or row["Unit_monthly"],
            "Suggested Par": round(row["Suggested Par"], 2),
        })

    return {"result": result}