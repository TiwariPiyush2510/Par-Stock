from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def calculate_final_stock(suggested_par, stock_in_hand):
    surplus = stock_in_hand - suggested_par
    if surplus >= suggested_par:
        return 0
    else:
        return round(suggested_par + max(0, suggested_par - stock_in_hand), 2)

@app.post("/calculate/")
async def calculate_par(
    monthly_file: UploadFile = File(...),
    weekly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None),
    ofi_file: UploadFile = File(None)
):
    # Read consumption data
    monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))
    weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))

    combined_df = pd.merge(weekly_df, monthly_df, on="Item Name", how="outer", suffixes=("_weekly", "_monthly"))
    combined_df.fillna(0, inplace=True)

    results = []
    for _, row in combined_df.iterrows():
        item = row["Item Name"]
        item_code = row.get("Item Code_weekly") or row.get("Item Code_monthly")
        unit = row.get("Unit_weekly") or row.get("Unit_monthly")

        weekly_total = row.get("Quantity_weekly", 0)
        monthly_total = row.get("Quantity_monthly", 0)

        weekly_avg = weekly_total / 7
        monthly_avg = monthly_total / 30
        suggested_par = round(max(weekly_avg, monthly_avg), 2)

        results.append({
            "Item": item,
            "Item Code": item_code,
            "Unit": unit,
            "Suggested Par": suggested_par,
            "Stock in Hand": 0,
            "Final Stock Needed": suggested_par  # initial assumption before frontend update
        })

    df = pd.DataFrame(results)

    # Match Barakat items
    if barakat_file:
        barakat_df = pd.read_excel(BytesIO(await barakat_file.read()), header=None)
        barakat_names = barakat_df.iloc[:, 1].str.strip().str.lower().tolist()
        df["Supplier"] = df["Item"].str.strip().str.lower().apply(lambda x: "Barakat" if x in barakat_names else "")

    # Match OFI items
    if ofi_file:
        ofi_df = pd.read_excel(BytesIO(await ofi_file.read()), header=None)
        ofi_names = ofi_df.iloc[:, 1].str.strip().str.lower().tolist()
        df["Supplier"] = df.apply(
            lambda row: "OFI" if row["Item"].strip().lower() in ofi_names else row["Supplier"], axis=1
        )

    return df.to_dict(orient="records")