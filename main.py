from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from typing import List

app = FastAPI()

# Allow frontend access (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None),
    ofi_file: UploadFile = File(None)
):
    try:
        # Read uploaded Excel files
        weekly_df = pd.read_excel(weekly_file.file)
        monthly_df = pd.read_excel(monthly_file.file)

        # Check for required column
        if "Quantity" not in weekly_df.columns or "Quantity" not in monthly_df.columns:
            return {"error": "Column not found: Quantity"}

        # Group by item and average daily consumption
        def get_daily_average(df):
            grouped = df.groupby("Item Name")["Quantity"].sum().reset_index()
            return grouped

        weekly_avg = get_daily_average(weekly_df)
        weekly_avg["Weekly Avg"] = weekly_avg["Quantity"] / 7
        monthly_avg = get_daily_average(monthly_df)
        monthly_avg["Monthly Avg"] = monthly_avg["Quantity"] / 30

        merged = pd.merge(weekly_avg[["Item Name", "Weekly Avg"]],
                          monthly_avg[["Item Name", "Monthly Avg"]],
                          on="Item Name", how="outer")

        # Suggested Par = higher of the two averages
        merged["Suggested Par"] = merged[["Weekly Avg", "Monthly Avg"]].max(axis=1)

        # Merge in full details (Item Code, Unit, etc.) from monthly file
        full_details = monthly_df.drop_duplicates(subset="Item Name")[["Item Name", "Item Code", "Unit"]]
        final_df = pd.merge(merged, full_details, on="Item Name", how="left")

        # Prepare output
        result = []
        for _, row in final_df.iterrows():
            item_name = row["Item Name"]
            suggested_par = row["Suggested Par"]

            result.append({
                "Item": item_name,
                "Item Code": row.get("Item Code", ""),
                "Unit": row.get("Unit", ""),
                "Suggested Par": round(suggested_par, 2),
                "Stock in Hand": 0,
                "Expected Delivery": 0,
                "Final Stock Needed": round(suggested_par, 2),
                "Supplier": get_supplier(item_name, barakat_file, ofi_file)
            })

        return {"result": result}

    except Exception as e:
        return {"error": str(e)}

def get_supplier(item_name, barakat_file, ofi_file):
    try:
        item_name_lower = item_name.strip().lower()

        if barakat_file:
            barakat_df = pd.read_excel(barakat_file.file)
            if "Item Name" in barakat_df.columns:
                barakat_items = barakat_df["Item Name"].dropna().str.lower().tolist()
                if item_name_lower in barakat_items:
                    return "Barakat"

        if ofi_file:
            ofi_df = pd.read_excel(ofi_file.file)
            if "Item Name" in ofi_df.columns:
                ofi_items = ofi_df["Item Name"].dropna().str.lower().tolist()
                if item_name_lower in ofi_items:
                    return "OFI"

        return "Other"

    except:
        return "Other"