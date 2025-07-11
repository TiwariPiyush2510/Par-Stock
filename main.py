# main.py
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

@app.post("/calculate_par_stock/")
async def calculate_par_stock(
    request: Request,
    monthly: UploadFile = File(...),
    weekly: UploadFile = File(...),
    barakat: UploadFile = File(None),
    ofi: UploadFile = File(None),
):
    try:
        # Load consumption reports
        monthly_df = pd.read_excel(BytesIO(await monthly.read()))
        weekly_df = pd.read_excel(BytesIO(await weekly.read()))

        # Compute average daily usage
        monthly_df['Daily Avg'] = monthly_df['Quantity'] / 30
        weekly_df['Daily Avg'] = weekly_df['Quantity'] / 7

        # Merge & get max daily avg per item
        combined_df = pd.concat([monthly_df, weekly_df])
        daily_avg_df = combined_df.groupby(['Item Name', 'Item Code', 'Unit']).agg({'Daily Avg': 'max'}).reset_index()
        daily_avg_df = daily_avg_df.rename(columns={"Daily Avg": "Suggested Par"})

        # Load current stock from frontend-uploaded template
        stock_data = await request.form()
        current_stock = {}
        for key in stock_data:
            if key.startswith("stock_"):
                item = key.replace("stock_", "")
                try:
                    current_stock[item] = float(stock_data[key])
                except:
                    current_stock[item] = 0.0

        # Supplier detection (Barakat, OFI)
        supplier_map = {}
        if barakat:
            barakat_df = pd.read_excel(BytesIO(await barakat.read()))
            for item in barakat_df['Item Name']:
                supplier_map[item.strip().lower()] = 'Barakat'
        if ofi:
            ofi_df = pd.read_excel(BytesIO(await ofi.read()))
            for item in ofi_df['Item Name']:
                supplier_map[item.strip().lower()] = 'OFI'

        # Final calculation
        result = []
        for _, row in daily_avg_df.iterrows():
            item_name = row['Item Name']
            item_code = row['Item Code']
            unit = row['Unit']
            suggested_par = round(row['Suggested Par'], 2)
            stock_in_hand = round(current_stock.get(item_name, 0.0), 2)
            
            # Final stock logic
            carry_forward = stock_in_hand - suggested_par
            if carry_forward >= 0:
                final_needed = max(0, suggested_par - carry_forward)
            else:
                final_needed = suggested_par + abs(carry_forward)

            final_needed = round(final_needed, 2)

            supplier = supplier_map.get(item_name.strip().lower(), "")

            result.append({
                "Item": item_name,
                "Item Code": item_code,
                "Unit": unit,
                "Suggested Par": suggested_par,
                "Stock in Hand": stock_in_hand,
                "Final Stock Needed": final_needed,
                "Supplier": supplier,
            })

        return JSONResponse(content=result)

    except Exception as e:
        print("❌ Backend Error:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)