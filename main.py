# --- main.py ---

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from io import BytesIO

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...)
):
    try:
        # Read both Excel files
        weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))
        monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))

        # Clean column names
        for df in [weekly_df, monthly_df]:
            df.columns = df.columns.str.strip()

        # Group by Item Code and sum quantity
        weekly_grouped = weekly_df.groupby("Item Code").agg({
            "Quantity": "sum",
            "Item Name": "first",
            "Unit": "first",
        }).reset_index()
        weekly_grouped["Daily Avg"] = weekly_grouped["Quantity"] / 7

        monthly_grouped = monthly_df.groupby("Item Code").agg({
            "Quantity": "sum",
            "Item Name": "first",
            "Unit": "first",
        }).reset_index()
        monthly_grouped["Daily Avg"] = monthly_grouped["Quantity"] / 30

        # Merge on Item Code
        merged = pd.merge(weekly_grouped, monthly_grouped, on="Item Code", how="outer", suffixes=("_weekly", "_monthly"))
        merged.fillna("", inplace=True)

        # Calculate Suggested Par as max of daily averages
        merged["Suggested Par"] = merged[["Daily Avg_weekly", "Daily Avg_monthly"]].apply(lambda row: max(float(row[0] or 0), float(row[1] or 0)), axis=1)

        # Format results
        result = []
        for _, row in merged.iterrows():
            result.append({
                "Item Name": row["Item Name_weekly"] or row["Item Name_monthly"],
                "Item Code": row["Item Code"],
                "Unit": row["Unit_weekly"] or row["Unit_monthly"],
                "Suggested Par": round(row["Suggested Par"], 2),
                "Stock in Hand": 0,
                "Expected Delivery": 0,
                "Final Stock Needed": round(row["Suggested Par"], 2),
            })

        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})