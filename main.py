from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from io import BytesIO
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...)
):
    try:
        weekly_data = pd.read_excel(BytesIO(await weekly_file.read()))
        monthly_data = pd.read_excel(BytesIO(await monthly_file.read()))
        supplier_data = pd.read_excel(BytesIO(await supplier_file.read())) if supplier_file.filename.endswith(".xlsx") else pd.read_csv(BytesIO(await supplier_file.read()))

        weekly_avg = weekly_data.groupby("Item Name")["Quantity"].sum() / 7
        monthly_avg = monthly_data.groupby("Item Name")["Quantity"].sum() / 30
        combined = pd.concat([weekly_avg, monthly_avg], axis=1)
        combined.columns = ["Weekly Avg", "Monthly Avg"]
        combined["Suggested Par"] = combined.max(axis=1).round(2)

        # Prepare supplier file
        supplier_data["Item Name"] = supplier_data["Item Name"].astype(str).str.strip().str.upper()
        combined.index = combined.index.str.strip().str.upper()
        matched = supplier_data[supplier_data["Item Name"].str.upper().isin(combined.index)]

        results = []
        for _, row in matched.iterrows():
            item_name = row["Item Name"].strip().upper()
            suggested_par = combined.loc[item_name, "Suggested Par"] if item_name in combined.index else 0
            results.append({
                "Item": row["Item Name"],
                "Item Code": row.get("Item Code", ""),
                "Unit": row.get("Unit", ""),
                "Suggested Par": round(suggested_par, 2),
                "Stock in Hand": 0,
                "Expected Delivery": 0,
                "Final Stock Needed": 0,
                "Supplier": row.get("Supplier", "")
            })

        return JSONResponse(content=results)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)