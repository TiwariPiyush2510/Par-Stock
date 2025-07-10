from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from io import BytesIO

app = FastAPI()

# CORS to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate-par-stock")
async def calculate_par_stock(weekly_file: UploadFile = File(...), monthly_file: UploadFile = File(...)):
    try:
        weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))
        monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))
    except Exception as e:
        return {"error": f"Failed to read Excel files: {str(e)}"}

    combined_items = pd.concat([weekly_df[['Item Code', 'Item Name', 'Unit', 'Quantity']],
                                monthly_df[['Item Code', 'Item Name', 'Unit', 'Quantity']]])
    
    # Group by Item Code and get totals
    weekly_total = weekly_df.groupby('Item Code')['Quantity'].sum() / 7
    monthly_total = monthly_df.groupby('Item Code')['Quantity'].sum() / 30
    suggested_par = pd.concat([weekly_total, monthly_total], axis=1).max(axis=1)

    item_info = combined_items.drop_duplicates('Item Code').set_index('Item Code')[['Item Name', 'Unit']]

    # Combine everything
    result = pd.DataFrame({
        'Suggested Par': suggested_par,
        'Item Name': item_info['Item Name'],
        'Unit': item_info['Unit']
    }).reset_index()

    return result.to_dict(orient="records")