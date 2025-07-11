from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_daily_average(df: pd.DataFrame, days: int) -> pd.DataFrame:
    df["Daily Average"] = df["Total Quantity"] / days
    return df

def calculate_par_stock(weekly: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    weekly_avg = get_daily_average(weekly.copy(), 7)
    monthly_avg = get_daily_average(monthly.copy(), 30)

    merged = pd.merge(weekly_avg, monthly_avg, on="Item Code", suffixes=("_weekly", "_monthly"))
    merged["Suggested Par"] = merged[["Daily Average_weekly", "Daily Average_monthly"]].max(axis=1)

    merged["Item"] = merged["Item_weekly"]
    merged["Unit"] = merged["Unit_weekly"]
    merged["Final Stock Needed"] = merged["Suggested Par"]  # Placeholder

    return merged[["Item", "Item Code", "Unit", "Suggested Par", "Final Stock Needed"]]

@app.post("/calculate")
async def calculate_par(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None)
):
    weekly_data = pd.read_excel(BytesIO(await weekly_file.read()))
    monthly_data = pd.read_excel(BytesIO(await monthly_file.read()))

    result_df = calculate_par_stock(weekly_data, monthly_data)

    if barakat_file:
        barakat_df = pd.read_excel(BytesIO(await barakat_file.read()))
        barakat_item_codes = set(barakat_df["Item Code"].astype(str))
        result_df["Supplier"] = result_df["Item Code"].astype(str).apply(lambda code: "Barakat" if code in barakat_item_codes else "Other")
    else:
        result_df["Supplier"] = "Other"

    result = result_df.to_dict(orient="records")
    return {"result": result}