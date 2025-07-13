from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import uvicorn
import os

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with frontend domain for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def parse_file(file: UploadFile) -> pd.DataFrame:
    ext = os.path.splitext(file.filename)[-1].lower()
    if ext == ".csv":
        return pd.read_csv(file.file)
    elif ext in [".xls", ".xlsx"]:
        return pd.read_excel(file.file)
    else:
        raise ValueError("Unsupported file format")

@app.post("/calculate_par_stock")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    supplier_file: UploadFile = File(...),
):
    try:
        # Parse files
        weekly_df = parse_file(weekly_file)
        monthly_df = parse_file(monthly_file)
        supplier_df = parse_file(supplier_file)

        # Clean column names
        weekly_df.columns = [str(c).strip() for c in weekly_df.columns]
        monthly_df.columns = [str(c).strip() for c in monthly_df.columns]
        supplier_df.columns = [str(c).strip() for c in supplier_df.columns]

        # Calculate daily averages
        def daily_avg(df):
            return df.groupby("Item")["Quantity"].sum() / 7

        weekly_avg = daily_avg(weekly_df)
        monthly_avg = daily_avg(monthly_df)
        par_stock = pd.concat([weekly_avg, monthly_avg], axis=1).max(axis=1).reset_index()
        par_stock.columns = ["Item", "Suggested Par"]

        # Merge with supplier data
        result = pd.merge(par_stock, supplier_df, on="Item", how="inner")

        # Fill defaults
        result["Stock in Hand"] = 0
        result["Expected Delivery"] = 0

        # Compute Final Stock Needed dynamically (initially 0)
        result["Final Stock Needed"] = 0

        # Reorder for frontend
        columns = ["Item", "Item Code", "Unit", "Suggested Par", "Stock in Hand", "Expected Delivery", "Final Stock Needed", "Supplier"]
        for col in columns:
            if col not in result.columns:
                result[col] = ""
        result = result[columns]

        return result.to_dict(orient="records")

    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)