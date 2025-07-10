
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

def calculate_par_stock(weekly_df, monthly_df):
    combined_df = pd.concat([weekly_df, monthly_df], ignore_index=True)
    combined_df = combined_df.groupby(['Item', 'Item Code', 'Unit'], as_index=False).sum()

    weekly_total = weekly_df.groupby(['Item', 'Item Code', 'Unit'], as_index=False).sum()
    monthly_total = monthly_df.groupby(['Item', 'Item Code', 'Unit'], as_index=False).sum()

    weekly_total['Weekly Avg'] = weekly_total['Quantity'] / 7
    monthly_total['Monthly Avg'] = monthly_total['Quantity'] / 30

    merged = pd.merge(weekly_total, monthly_total, on=['Item', 'Item Code', 'Unit'], suffixes=('_week', '_month'))
    merged['Suggested Par'] = merged[['Weekly Avg', 'Monthly Avg']].max(axis=1).round(2)

    merged = merged[['Item', 'Item Code', 'Unit', 'Suggested Par']]

    return merged.to_dict(orient="records")

@app.post("/calculate")
async def calculate(weekly_file: UploadFile = File(...), monthly_file: UploadFile = File(...)):
    weekly_bytes = await weekly_file.read()
    monthly_bytes = await monthly_file.read()

    weekly_df = pd.read_excel(BytesIO(weekly_bytes))
    monthly_df = pd.read_excel(BytesIO(monthly_bytes))

    result = calculate_par_stock(weekly_df, monthly_df)
    return {"result": result}
