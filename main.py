from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from typing import List

app = FastAPI()

# Allow frontend access (update with your actual frontend domain if needed)
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
    monthly_file: UploadFile = File(...),
):
    try:
        weekly_df = pd.read_excel(weekly_file.file)
        monthly_df = pd.read_excel(monthly_file.file)

        # Normalize column names
        weekly_df.columns = weekly_df.columns.str.strip()
        monthly_df.columns = monthly_df.columns.str.strip()

        # Merge both files on Item Code
        merged_df = pd.merge(
            weekly_df,
            monthly_df,
            on=["Item Code"],
            suffixes=("_weekly", "_monthly"),
            how="outer",
        )

        merged_df.fillna(0, inplace=True)

        result = []
        for _, row in merged_df.iterrows():
            item = row.get("Item_weekly") or row.get("Item_monthly") or "Unknown"
            item_code = row.get("Item Code")
            unit = row.get("Unit_weekly") or row.get("Unit_monthly") or ""

            weekly_total = row.get("Total Usage_weekly", 0)
            monthly_total = row.get("Total Usage_monthly", 0)

            weekly_avg = weekly_total / 7 if weekly_total else 0
            monthly_avg = monthly_total / 30 if monthly_total else 0

            suggested_par = round(max(weekly_avg, monthly_avg), 2)

            result.append({
                "Item": item,
                "Item Code": item_code,
                "Unit": unit,
                "Suggested Par": suggested_par
            })

        return {"result": result}

    except Exception as e:
        return {"error": str(e)}
