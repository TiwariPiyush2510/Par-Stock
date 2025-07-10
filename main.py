from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate")
async def calculate_par_stock(weekly_file: UploadFile = File(...), monthly_file: UploadFile = File(...)):
    weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))
    monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))

    # Group and sum by Item and Item Code
    weekly_summary = weekly_df.groupby(["Item", "Item Code", "Unit"], as_index=False)["Quantity"].sum()
    weekly_summary["Weekly Avg"] = weekly_summary["Quantity"] / 7

    monthly_summary = monthly_df.groupby(["Item", "Item Code", "Unit"], as_index=False)["Quantity"].sum()
    monthly_summary["Monthly Avg"] = monthly_summary["Quantity"] / 30

    # Merge both summaries
    merged = pd.merge(weekly_summary, monthly_summary, on=["Item", "Item Code", "Unit"], how="outer", suffixes=("_weekly", "_monthly")).fillna(0)

    # Determine suggested par
    merged["Suggested Par"] = merged[["Weekly Avg", "Monthly Avg"]].max(axis=1)

    result = []
    for _, row in merged.iterrows():
        result.append({
            "Item": row["Item"],
            "Item Code": row["Item Code"],
            "Unit": row["Unit"],
            "Suggested Par": round(row["Suggested Par"], 2),
        })

    return {"result": result}
