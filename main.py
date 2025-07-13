from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import uvicorn
import io
import os

app = FastAPI()

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def read_file(file: UploadFile):
    ext = os.path.splitext(file.filename)[1]
    content = file.file.read()
    if ext == ".csv":
        return pd.read_csv(io.BytesIO(content))
    else:
        return pd.read_excel(io.BytesIO(content))

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    weekly_df = read_file(weekly_file)
    monthly_df = read_file(monthly_file)
    supplier_df = read_file(supplier_file)

    # Preprocess and normalize
    weekly_avg = weekly_df.groupby("Item")["Qty"].sum() / 7
    monthly_avg = monthly_df.groupby("Item")["Qty"].sum() / 30

    suggested_par = pd.concat([weekly_avg, monthly_avg], axis=1).max(axis=1).reset_index()
    suggested_par.columns = ["Item", "Suggested Par"]

    # Normalize item names
    supplier_df["Item"] = supplier_df["Item"].str.strip().str.upper()
    suggested_par["Item"] = suggested_par["Item"].str.strip().str.upper()

    merged = pd.merge(supplier_df, suggested_par, on="Item", how="inner")

    merged["Stock in Hand"] = 0
    merged["Expected Delivery"] = 0
    merged["Final Stock Needed"] = 0

    # Reorder
    cols = [
        "Item", "Item Code", "Unit", "Suggested Par",
        "Stock in Hand", "Expected Delivery", "Final Stock Needed", "Supplier"
    ]
    merged = merged[cols]

    return JSONResponse(content=merged.to_dict(orient="records"))