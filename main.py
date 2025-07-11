from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import io

app = FastAPI()

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/calculate")
async def calculate_par_stock(
    weekly_file: UploadFile = File(...),
    monthly_file: UploadFile = File(...),
    barakat_file: UploadFile = File(None),
    ofi_file: UploadFile = File(None)
):
    try:
        # Read weekly & monthly
        weekly_df = pd.read_excel(io.BytesIO(await weekly_file.read()))
        monthly_df = pd.read_excel(io.BytesIO(await monthly_file.read()))

        # Normalize headers
        weekly_df.columns = weekly_df.columns.str.strip()
        monthly_df.columns = monthly_df.columns.str.strip()

        # Daily Avg
        weekly_df["Daily Avg"] = weekly_df["Quantity"] / 7
        monthly_df["Daily Avg"] = monthly_df["Quantity"] / 30

        # Merge both
        merged = pd.merge(
            weekly_df,
            monthly_df,
            on="Item Name",
            suffixes=("_weekly", "_monthly")
        )

        merged["Suggested Par"] = merged[["Daily Avg_weekly", "Daily Avg_monthly"]].max(axis=1)

        # Build result
        result = merged[["Item Name", "Item Code_weekly", "Unit_weekly", "Suggested Par"]].copy()
        result.columns = ["Item", "Item Code", "Unit", "Suggested Par"]
        result["Stock in Hand"] = 0
        result["Final Stock Needed"] = result["Suggested Par"]  # default before edits
        result["Supplier"] = ""

        # Helper to tag supplier
        def tag_supplier(file: UploadFile, name: str):
            if file:
                df = pd.read_excel(io.BytesIO(file.file.read()))
                df.columns = df.columns.str.strip()
                item_list = df["Item Name"].astype(str).str.strip().str.lower().tolist()
                result.loc[result["Item"].astype(str).str.strip().str.lower().isin(item_list), "Supplier"] = name

        tag_supplier(barakat_file, "Barakat")
        tag_supplier(ofi_file, "OFI")

        # Round for display
        result["Suggested Par"] = result["Suggested Par"].round(2)
        result["Final Stock Needed"] = result["Final Stock Needed"].round(2)

        return JSONResponse(content=result.to_dict(orient="records"))

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)