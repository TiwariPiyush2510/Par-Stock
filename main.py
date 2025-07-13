from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import pandas as pd
from io import BytesIO
import uvicorn

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def read_file(file: UploadFile):
    filename = file.filename
    content = file.file.read()
    if filename.endswith(".csv"):
        return pd.read_csv(BytesIO(content))
    else:
        return pd.read_excel(BytesIO(content))

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    # Read files
    weekly_df = read_file(weekly_file)
    monthly_df = read_file(monthly_file)
    supplier_df = read_file(supplier_file)

    # Clean headers
    weekly_df.columns = weekly_df.columns.str.strip()
    monthly_df.columns = monthly_df.columns.str.strip()
    supplier_df.columns = supplier_df.columns.str.strip()

    # Combine consumption data
    def clean_consumption(df):
        df = df.copy()
        df.columns = df.columns.str.strip()
        df = df.rename(columns={
            'Item Name': 'Item',
            'Item': 'Item',
            'Item Code': 'Item Code',
            'Unit': 'Unit',
            'Quantity': 'Quantity'
        })
        return df[['Item', 'Unit', 'Quantity']]

    weekly = clean_consumption(weekly_df)
    monthly = clean_consumption(monthly_df)

    # Compute averages
    weekly_avg = weekly.groupby(['Item', 'Unit'])['Quantity'].mean() / 7
    monthly_avg = monthly.groupby(['Item', 'Unit'])['Quantity'].mean() / 30

    combined = pd.concat([weekly_avg, monthly_avg], axis=1).fillna(0)
    combined['Suggested Par'] = combined.max(axis=1)
    combined = combined.reset_index()[['Item', 'Unit', 'Suggested Par']]

    # Match supplier items
    supplier_df = supplier_df.rename(columns={
        'Item Name': 'Item',
        'Item': 'Item',
        'Item Code': 'Item Code',
        'Unit': 'Unit'
    })

    result = pd.merge(supplier_df, combined, on='Item', how='left')
    result['Suggested Par'] = result['Suggested Par'].fillna(0)
    result['Stock in Hand'] = 0
    result['Expected Delivery'] = 0
    result['Final Stock Needed'] = 0

    # Extract supplier name from filename
    supplier_name = supplier_file.filename.split('.')[0].strip().split(' ')[0]
    result['Supplier'] = supplier_name

    # Reorder columns
    result = result[['Item', 'Item Code', 'Unit', 'Suggested Par', 'Stock in Hand', 'Expected Delivery', 'Final Stock Needed', 'Supplier']]

    # Convert to dict
    return result.to_dict(orient='records')