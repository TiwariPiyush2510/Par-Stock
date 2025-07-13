from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import uvicorn
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://preeminent-choux-a8ea17.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def read_file(upload: UploadFile):
    filename = upload.filename.lower()
    if filename.endswith(".csv"):
        return pd.read_csv(upload.file)
    elif filename.endswith(".xlsx"):
        return pd.read_excel(upload.file)
    return pd.DataFrame()

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    # Read files
    weekly_df = read_file(weekly_file)
    monthly_df = read_file(monthly_file)
    supplier_df = read_file(supplier_file)

    # Clean column names
    weekly_df.columns = weekly_df.columns.str.strip()
    monthly_df.columns = monthly_df.columns.str.strip()
    supplier_df.columns = supplier_df.columns.str.strip()

    # Calculate Daily Averages
    weekly_df["Item Name"] = weekly_df["Item Name"].astype(str).str.strip().str.lower()
    monthly_df["Item Name"] = monthly_df["Item Name"].astype(str).str.strip().str.lower()
    supplier_df["Item Name"] = supplier_df["Item Name"].astype(str).str.strip().str.lower()

    weekly_df["Daily Avg"] = weekly_df["Quantity"] / 7
    monthly_df["Daily Avg"] = monthly_df["Quantity"] / 30

    # Merge weekly and monthly
    merged = pd.merge(
        weekly_df[["Item Name", "Daily Avg"]],
        monthly_df[["Item Name", "Daily Avg"]],
        on="Item Name",
        suffixes=("_weekly", "_monthly"),
        how="outer"
    ).fillna(0)

    merged["Suggested Par"] = merged[["Daily Avg_weekly", "Daily Avg_monthly"]].max(axis=1)

    # Merge with supplier
    required_cols = {"Item Name", "Item Code", "Unit"}
    if not required_cols.issubset(set(supplier_df.columns)):
        return JSONResponse(content={"error": "Missing required columns in supplier file"}, status_code=400)

    final = pd.merge(
        merged,
        supplier_df[["Item Name", "Item Code", "Unit"]],
        on="Item Name",
        how="inner"
    )

    final["Suggested Par"] = final["Suggested Par"].round(2)

    # Prepare result
    result = final.rename(columns={"Item Name": "Item"})[["Item", "Item Code", "Unit", "Suggested Par"]]
    result["Stock in Hand"] = 0
    result["Expected Delivery"] = 0
    result["Final Stock Needed"] = 0
    result["Supplier"] = os.path.splitext(supplier_file.filename)[0].split(" ")[0]

    return JSONResponse(content=result.to_dict(orient="records"))