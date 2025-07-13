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
    else:
        return pd.DataFrame()

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    weekly_df = read_file(weekly_file)
    monthly_df = read_file(monthly_file)
    supplier_df = read_file(supplier_file)

    weekly_df["Daily Avg"] = weekly_df["Quantity"] / 7
    monthly_df["Daily Avg"] = monthly_df["Quantity"] / 30

    merged = pd.merge(
        weekly_df[["Item Name", "Daily Avg"]],
        monthly_df[["Item Name", "Daily Avg"]],
        on="Item Name",
        suffixes=("_weekly", "_monthly"),
        how="outer"
    ).fillna(0)

    merged["Suggested Par"] = merged[["Daily Avg_weekly", "Daily Avg_monthly"]].max(axis=1)

    if "Item Name" in supplier_df.columns:
        supplier_df["Item Name"] = supplier_df["Item Name"].str.strip().str.lower()
        merged["Item Name"] = merged["Item Name"].str.strip().str.lower()

        final = pd.merge(
            merged,
            supplier_df,
            on="Item Name",
            how="inner"
        )

        final["Suggested Par"] = final["Suggested Par"].round(2)
        result = final[["Item Name", "Item Code", "Unit", "Suggested Par"]].copy()
        result["Stock in Hand"] = 0
        result["Expected Delivery"] = 0
        result["Final Stock Needed"] = 0
        result["Supplier"] = os.path.splitext(supplier_file.filename)[0].split(" ")[0]

        result.rename(columns={"Item Name": "Item"}, inplace=True)
        return JSONResponse(content=result.to_dict(orient="records"))

    return JSONResponse(content={"error": "Supplier file format invalid"}, status_code=400)