from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from io import BytesIO

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate/")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...)
):
    weekly_content = await weekly_file.read()
    monthly_content = await monthly_file.read()

    df_weekly = pd.read_excel(BytesIO(weekly_content))
    df_monthly = pd.read_excel(BytesIO(monthly_content))

    # Sum quantities per item for weekly and monthly
    weekly_group = df_weekly.groupby("Item Code").agg({
        "Quantity": "sum",
        "Item Name": "first",
        "Unit": "first"
    }).reset_index()
    weekly_group["Weekly Avg"] = weekly_group["Quantity"] / 7

    monthly_group = df_monthly.groupby("Item Code").agg({
        "Quantity": "sum",
        "Item Name": "first",
        "Unit": "first"
    }).reset_index()
    monthly_group["Monthly Avg"] = monthly_group["Quantity"] / 30

    # Merge both
    merged = pd.merge(weekly_group, monthly_group, on="Item Code", how="outer", suffixes=('_week', '_month'))

    # Fill missing fields
    for col in ["Item Name_week", "Item Name_month", "Unit_week", "Unit_month"]:
        if col not in merged.columns:
            merged[col] = ""

    merged["Item Name"] = merged["Item Name_week"].combine_first(merged["Item Name_month"])
    merged["Unit"] = merged["Unit_week"].combine_first(merged["Unit_month"])

    merged["Weekly Avg"] = merged["Weekly Avg"].fillna(0)
    merged["Monthly Avg"] = merged["Monthly Avg"].fillna(0)

    merged["Suggested Par"] = merged[["Weekly Avg", "Monthly Avg"]].max(axis=1)
    merged = merged[["Item Name", "Item Code", "Unit", "Suggested Par"]]

    return merged.to_dict(orient="records")