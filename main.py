from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from io import BytesIO

app = FastAPI()

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def calculate_par_stock(weekly_df, monthly_df, barakat_items, ofi_items):
    combined_df = pd.concat([weekly_df, monthly_df], ignore_index=True)

    grouped = combined_df.groupby(['Item Name', 'Item Code', 'Unit']).agg({
        'Quantity': 'sum'
    }).reset_index()

    weekly_total = weekly_df.groupby(['Item Name'])['Quantity'].sum()
    monthly_total = monthly_df.groupby(['Item Name'])['Quantity'].sum()

    result = []
    all_items = set(weekly_total.index).union(monthly_total.index)

    for item in all_items:
        weekly_avg = weekly_total.get(item, 0) / 7
        monthly_avg = monthly_total.get(item, 0) / 30
        suggested_par = round(max(weekly_avg, monthly_avg), 2)

        item_row = grouped[grouped['Item Name'] == item].iloc[0]
        supplier = ''
        if item.strip().lower() in barakat_items:
            supplier = 'Barakat'
        elif item.strip().lower() in ofi_items:
            supplier = 'OFI'

        result.append({
            'Item': item_row['Item Name'],
            'Item Code': item_row['Item Code'],
            'Unit': item_row['Unit'],
            'Suggested Par': suggested_par,
            'Stock in Hand': 0,
            'Final Stock Needed': suggested_par,
            'Supplier': supplier
        })

    return result

@app.post("/calculate/")
async def calculate(
    monthly_file: UploadFile = File(...),
    weekly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None),
    ofi_file: UploadFile = File(None)
):
    try:
        # Load consumption reports
        monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))
        weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))

        # Normalize headers
        for df in [monthly_df, weekly_df]:
            df.columns = [col.strip() for col in df.columns]

        # Load supplier item names
        def extract_item_names(file):
            if file is None:
                return set()
            df = pd.read_excel(BytesIO(file))
            df.columns = [str(c).strip() for c in df.columns]
            return set(df.iloc[:, 1].dropna().astype(str).str.strip().str.lower())

        barakat_items = extract_item_names(await barakat_file.read()) if barakat_file else set()
        ofi_items = extract_item_names(await ofi_file.read()) if ofi_file else set()

        # Process logic
        result = calculate_par_stock(weekly_df, monthly_df, barakat_items, ofi_items)

        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})