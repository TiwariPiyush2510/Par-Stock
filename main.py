from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
import io

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to your frontend domain
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
    # Read all files into DataFrames
    def read_file(upload: UploadFile):
        if upload.filename.endswith('.csv'):
            return pd.read_csv(upload.file)
        else:
            return pd.read_excel(upload.file)

    weekly_df = read_file(weekly_file)
    monthly_df = read_file(monthly_file)
    supplier_df = read_file(supplier_file)

    # Normalize column names
    weekly_df.columns = [c.strip() for c in weekly_df.columns]
    monthly_df.columns = [c.strip() for c in monthly_df.columns]
    supplier_df.columns = [c.strip() for c in supplier_df.columns]

    # Clean and get average daily consumption
    weekly_df["Daily"] = weekly_df["Qty"] / 7
    monthly_df["Daily"] = monthly_df["Qty"] / 30

    combined_df = pd.concat([weekly_df[["Item", "Daily"]], monthly_df[["Item", "Daily"]]])
    avg_df = combined_df.groupby("Item", as_index=False).mean()
    avg_df.rename(columns={"Daily": "Suggested Par"}, inplace=True)

    # Join with supplier data
    supplier_df["Item"] = supplier_df["Item"].str.strip().str.upper()
    avg_df["Item"] = avg_df["Item"].str.strip().str.upper()

    merged = pd.merge(supplier_df, avg_df, on="Item", how="left")
    merged["Suggested Par"] = merged["Suggested Par"].fillna(0)

    # Add default values for frontend fields
    merged["Stock in Hand"] = 0
    merged["Expected Delivery"] = 0
    merged["Final Stock Needed"] = 0

    # Format for frontend
    result = merged.to_dict(orient="records")
    return result