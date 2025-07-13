from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...),
):
    # Load all files into DataFrames
    weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))
    monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))
    supplier_df = pd.read_excel(BytesIO(await supplier_file.read())) if supplier_file.filename.endswith(".xlsx") else pd.read_csv(BytesIO(await supplier_file.read()))

    # Clean headers
    weekly_df.columns = [c.strip() for c in weekly_df.columns]
    monthly_df.columns = [c.strip() for c in monthly_df.columns]
    supplier_df.columns = [c.strip() for c in supplier_df.columns]

    # Daily averages
    weekly_df["Daily Avg"] = weekly_df["Consumption"] / 7
    monthly_df["Daily Avg"] = monthly_df["Consumption"] / 30

    # Use higher of two averages
    combined = pd.merge(weekly_df[["Item Name", "Item Code", "Daily Avg"]],
                        monthly_df[["Item Name", "Item Code", "Daily Avg"]],
                        on=["Item Name", "Item Code"], suffixes=('_weekly', '_monthly'))
    combined["Suggested Par"] = combined[["Daily Avg_weekly", "Daily Avg_monthly"]].max(axis=1)

    # Merge with units
    unit_map = weekly_df[["Item Name", "Unit"]].drop_duplicates()
    combined = pd.merge(combined, unit_map, on="Item Name", how="left")

    # Match with supplier file by Item Name
    supplier_df["Item Name"] = supplier_df["Item Name"].str.strip().str.upper()
    combined["Item Name"] = combined["Item Name"].str.strip().str.upper()
    final = pd.merge(combined, supplier_df[["Item Name"]], on="Item Name", how="inner")

    # Add supplier name column
    supplier_name = supplier_file.filename.split(".")[0].strip().title()
    final["Supplier"] = supplier_name

    # Clean and return JSON
    final = final[["Item Name", "Item Code", "Unit", "Suggested Par", "Supplier"]]
    final = final.rename(columns={"Item Name": "Item"})

    final["Stock in Hand"] = 0
    final["Expected Delivery"] = 0
    final["Final Stock Needed"] = 0

    return final.to_dict(orient="records")