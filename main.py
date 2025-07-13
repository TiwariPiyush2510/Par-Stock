from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
import io
import os

app = FastAPI()

# Allow frontend access (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# UOM conversion map
conversion_map = {
    ("CASE", "KGS"): 10,
    ("CASE", "PCS"): 24,
    ("CASE", "BTL"): 6,
    ("BOX", "PCS"): 10,
    ("PACK", "PCS"): 12,
    # Add more if needed
}

def convert_unit(supplier_qty, supplier_uom, report_uom):
    if supplier_uom == report_uom:
        return supplier_qty
    return supplier_qty * conversion_map.get((supplier_uom, report_uom), 1)

def read_file(upload: UploadFile) -> pd.DataFrame:
    content = upload.file.read()
    extension = os.path.splitext(upload.filename)[1].lower()
    if extension == ".csv":
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    else:
        df = pd.read_excel(io.BytesIO(content))
    return df

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    weekly_df = read_file(weekly_file)
    monthly_df = read_file(monthly_file)
    supplier_df = read_file(supplier_file)

    supplier_name = supplier_file.filename.split()[0].strip()

    weekly_avg = weekly_df.groupby("Item Name")["Quantity"].sum() / 7
    monthly_avg = monthly_df.groupby("Item Name")["Quantity"].sum() / 30
    suggested_par = pd.concat([weekly_avg, monthly_avg], axis=1).max(axis=1).reset_index()
    suggested_par.columns = ["Item Name", "Suggested Par"]

    merged = suggested_par.merge(weekly_df[["Item Name", "Unit"]].drop_duplicates(), on="Item Name", how="left")
    merged["Stock in Hand"] = 0
    merged["Expected Delivery"] = 0

    supplier_df.columns = supplier_df.columns.str.strip()
    supplier_df["Item Name"] = supplier_df["Item Name"].str.strip().str.upper()
    merged["Item Name"] = merged["Item Name"].str.strip().str.upper()

    supplier_items = supplier_df[["Item Name", "Item Code", "Unit"]].drop_duplicates()
    final_df = pd.merge(merged, supplier_items, on="Item Name", how="left")

    # Reorder and fill
    final_df["Supplier"] = supplier_name
    final_df["Final Stock Needed"] = 0

    final_df = final_df[
        ["Item Name", "Item Code", "Unit", "Suggested Par", "Stock in Hand", "Expected Delivery", "Final Stock Needed", "Supplier"]
    ]

    final_df.fillna({"Item Code": "", "Unit": ""}, inplace=True)

    return final_df.to_dict(orient="records")