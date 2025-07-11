from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from typing import List
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def clean_string(s):
    return str(s).strip().lower()


@app.post("/calculate/")
async def calculate_par_stock(
    monthly_file: UploadFile = File(...),
    weekly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None),
):
    # Read Excel files
    monthly_data = pd.read_excel(BytesIO(await monthly_file.read()))
    weekly_data = pd.read_excel(BytesIO(await weekly_file.read()))

    # Ensure correct columns exist
    if "Item Code" not in monthly_data.columns or "Quantity" not in monthly_data.columns:
        return {"error": "Invalid Monthly File format"}

    if "Item Code" not in weekly_data.columns or "Quantity" not in weekly_data.columns:
        return {"error": "Invalid Weekly File format"}

    # Combine and compute average per day
    monthly_grouped = monthly_data.groupby("Item Code").agg({"Quantity": "sum"}).reset_index()
    weekly_grouped = weekly_data.groupby("Item Code").agg({"Quantity": "sum"}).reset_index()

    monthly_grouped["Monthly Avg"] = monthly_grouped["Quantity"] / 30
    weekly_grouped["Weekly Avg"] = weekly_grouped["Quantity"] / 7

    merged = pd.merge(monthly_grouped[["Item Code", "Monthly Avg"]],
                      weekly_grouped[["Item Code", "Weekly Avg"]],
                      on="Item Code", how="outer")

    merged.fillna(0, inplace=True)
    merged["Suggested Par"] = merged[["Monthly Avg", "Weekly Avg"]].max(axis=1)

    # Add Item Name, Unit etc. from monthly file
    item_info = monthly_data.drop_duplicates(subset="Item Code")[["Item Code", "Item Name", "Unit"]]
    merged = pd.merge(merged, item_info, on="Item Code", how="left")

    merged["Stock in Hand"] = 0
    merged["Final Stock Needed"] = merged["Suggested Par"]

    # Handle supplier tagging using Item Name from Barakat file
    barakat_items = []
    if barakat_file is not None:
        barakat_df = pd.read_excel(BytesIO(await barakat_file.read()))
        barakat_items = barakat_df.iloc[:, 1].dropna().apply(clean_string).tolist()

    merged["Supplier"] = merged["Item Name"].apply(lambda x: "Barakat" if clean_string(x) in barakat_items else "")

    # Reorder and rename columns
    merged = merged[["Item Name", "Item Code", "Unit", "Suggested Par", "Stock in Hand", "Final Stock Needed", "Supplier"]]
    merged.rename(columns={"Item Name": "Item"}, inplace=True)

    result = merged.to_dict(orient="records")
    return {"data": result}