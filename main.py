from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import uvicorn
from typing import Optional
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store uploaded supplier data in memory
supplier_data_cache = {}

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly: UploadFile = File(...),
    monthly: UploadFile = File(...),
    supplier: UploadFile = File(...)
):
    try:
        # Read weekly and monthly consumption
        weekly_df = read_file(weekly)
        monthly_df = read_file(monthly)
        supplier_df = read_file(supplier)

        # Clean column names
        weekly_df.columns = weekly_df.columns.str.strip()
        monthly_df.columns = monthly_df.columns.str.strip()
        supplier_df.columns = supplier_df.columns.str.strip()

        # Calculate daily averages
        weekly_avg = weekly_df.groupby("Item Name")["Quantity"].sum() / 7
        monthly_avg = monthly_df.groupby("Item Name")["Quantity"].sum() / 30
        par_stock = pd.concat([weekly_avg, monthly_avg], axis=1)
        par_stock.columns = ["weekly", "monthly"]
        par_stock["Suggested Par"] = par_stock.max(axis=1)

        # Prepare supplier file: match by Item Name (case-insensitive)
        supplier_df["Item Name"] = supplier_df["Item Name"].astype(str).str.strip().str.upper()
        supplier_items = supplier_df.set_index("Item Name")

        result = []
        for item, row in par_stock.iterrows():
            item_upper = item.strip().upper()
            suggested_par = round(row["Suggested Par"], 2)

            if item_upper in supplier_items.index:
                sup_row = supplier_items.loc[item_upper]
                unit = str(sup_row.get("Unit", ""))
                item_code = sup_row.get("Item Code", "")
                supplier_name = detect_supplier(supplier.filename)
            else:
                unit = ""
                item_code = ""
                supplier_name = "Unknown"

            result.append({
                "Item": item,
                "Item Code": item_code,
                "Unit": unit,
                "Suggested Par": suggested_par,
                "Stock in Hand": 0,
                "Expected Delivery": 0,
                "Final Stock Needed": suggested_par,
                "Supplier": supplier_name
            })

        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

def read_file(uploaded_file: UploadFile) -> pd.DataFrame:
    content = uploaded_file.file.read()
    if uploaded_file.filename.endswith(".csv"):
        return pd.read_csv(BytesIO(content))
    else:
        return pd.read_excel(BytesIO(content))

def detect_supplier(filename: str) -> str:
    filename = filename.lower()
    if "barakat" in filename:
        return "Barakat"
    elif "ofi" in filename:
        return "OFI"
    elif "ahlia" in filename:
        return "Al Ahlia"
    elif "emirates" in filename:
        return "Emirates Poultry"
    elif "harvey" in filename:
        return "Harvey and Brockess"
    else:
        return "Unknown"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)