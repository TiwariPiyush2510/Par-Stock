from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

class Item(BaseModel):
    item_code: str
    item_name: str
    unit: str
    suggested_par: float
    stock_in_hand: float
    final_stock_needed: float

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...)
):
    try:
        # Read files
        weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))
        monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))

        # Ensure expected columns
        expected_cols = ["Item Name", "Item Code", "Quantity", "Unit"]
        for df in [weekly_df, monthly_df]:
            if not all(col in df.columns for col in expected_cols):
                return {"error": "Missing required columns."}

        # Group and sum quantities
        weekly_grouped = weekly_df.groupby(["Item Code", "Item Name", "Unit"])["Quantity"].sum().reset_index()
        monthly_grouped = monthly_df.groupby(["Item Code", "Item Name", "Unit"])["Quantity"].sum().reset_index()

        # Calculate daily average
        weekly_grouped["Daily Avg"] = weekly_grouped["Quantity"] / 7
        monthly_grouped["Daily Avg"] = monthly_grouped["Quantity"] / 30

        # Merge
        merged = pd.merge(weekly_grouped, monthly_grouped, on=["Item Code", "Item Name", "Unit"], how="outer", suffixes=("_weekly", "_monthly")).fillna(0)

        # Suggested par = max of both daily averages
        merged["Suggested Par"] = merged[["Daily Avg_weekly", "Daily Avg_monthly"]].max(axis=1)

        # Default stock in hand = 0 for now
        merged["Stock in Hand"] = 0

        # Final stock needed = max(0, Suggested Par - Stock in Hand)
        merged["Final Stock Needed"] = merged["Suggested Par"]

        result = []
        for _, row in merged.iterrows():
            result.append({
                "item_code": row["Item Code"],
                "item_name": row["Item Name"],
                "unit": row["Unit"],
                "suggested_par": round(row["Suggested Par"], 2),
                "stock_in_hand": 0,
                "final_stock_needed": round(row["Final Stock Needed"], 2)
            })

        return result

    except Exception as e:
        return {"error": str(e)}