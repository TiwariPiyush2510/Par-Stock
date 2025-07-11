from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import io

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate_par_stock/")
async def calculate_par_stock(
    monthly_file: UploadFile = File(...),
    weekly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None),
    ofi_file: UploadFile = File(None)
):
    try:
        # Read uploaded files
        monthly_df = pd.read_excel(monthly_file.file)
        weekly_df = pd.read_excel(weekly_file.file)

        # Clean column names
        monthly_df.columns = monthly_df.columns.str.strip()
        weekly_df.columns = weekly_df.columns.str.strip()

        # Merge and compute average daily usage
        merged = pd.merge(monthly_df, weekly_df, on="Item Name", how="outer", suffixes=('_monthly', '_weekly')).fillna(0)
        merged["Monthly Avg"] = merged["Total Consumption_monthly"] / merged["Days_monthly"]
        merged["Weekly Avg"] = merged["Total Consumption_weekly"] / merged["Days_weekly"]
        merged["Suggested Par"] = merged[["Monthly Avg", "Weekly Avg"]].max(axis=1).round(2)

        # Read supplier files
        barakat_items = []
        ofi_items = []

        if barakat_file:
            barakat_df = pd.read_excel(barakat_file.file)
            barakat_items = barakat_df["Item Name"].str.strip().str.lower().tolist()

        if ofi_file:
            ofi_df = pd.read_excel(ofi_file.file)
            ofi_items = ofi_df["Item Name"].str.strip().str.lower().tolist()

        # Assign suppliers
        def get_supplier(item_name):
            name = item_name.strip().lower()
            if name in barakat_items:
                return "Barakat"
            elif name in ofi_items:
                return "OFI"
            else:
                return ""

        merged["Supplier"] = merged["Item Name"].apply(get_supplier)

        # Build response
        final_data = []
        for _, row in merged.iterrows():
            item = row["Item Name"]
            code = row.get("Item Code", "")
            unit = row.get("Unit", "")
            par = row["Suggested Par"]

            final_data.append({
                "Item": item,
                "Item Code": code,
                "Unit": unit,
                "Suggested Par": round(par, 2),
                "Stock in Hand": 0,
                "Final Stock Needed": round(par, 2),  # Initially same as par
                "Supplier": row["Supplier"]
            })

        return JSONResponse(content=final_data)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)