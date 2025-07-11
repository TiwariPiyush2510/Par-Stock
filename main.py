from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io

app = FastAPI()

# Allow frontend calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def process_file(file: UploadFile, days: int):
    contents = file.file.read()
    df = pd.read_excel(io.BytesIO(contents))
    df = df.rename(columns=lambda x: x.strip())
    df = df[["Item", "Item Code", "Unit", "Quantity"]]
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0)
    df = df.groupby(["Item", "Item Code", "Unit"], as_index=False)["Quantity"].sum()
    df["Daily Avg"] = df["Quantity"] / days
    return df

@app.post("/calculate")
async def calculate_par_stock(weekly_file: UploadFile = File(...), monthly_file: UploadFile = File(...)):
    weekly_df = process_file(weekly_file, 7)
    monthly_df = process_file(monthly_file, 30)

    merged = pd.merge(weekly_df, monthly_df, on=["Item", "Item Code", "Unit"], how="outer", suffixes=('_weekly', '_monthly'))
    merged = merged.fillna(0)

    merged["Suggested Par"] = merged[["Daily Avg_weekly", "Daily Avg_monthly"]].max(axis=1)
    merged = merged[["Item", "Item Code", "Unit", "Suggested Par"]]
    merged["Suggested Par"] = merged["Suggested Par"].round(2)

    return {"result": merged.to_dict(orient="records")}