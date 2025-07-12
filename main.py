from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from io import BytesIO

app = FastAPI()

# ✅ Allow your Netlify frontend origin (NO TRAILING SLASH!)
origins = [
    "https://preeminent-choux-a8ea17.netlify.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/calculate_par_stock")
async def calculate_par_stock(weekly_file: UploadFile = File(...),
                               monthly_file: UploadFile = File(...),
                               barakat_file: UploadFile = File(...),
                               ofi_file: UploadFile = File(...)):
    try:
        # Load weekly and monthly data
        weekly_df = pd.read_excel(BytesIO(await weekly_file.read()))
        monthly_df = pd.read_excel(BytesIO(await monthly_file.read()))

        # Calculate daily averages
        weekly_avg = weekly_df.groupby("Item")["Quantity"].sum() / 7
        monthly_avg = monthly_df.groupby("Item")["Quantity"].sum() / 30

        # Use the higher average
        par_stock = pd.DataFrame({
            "Suggested Par": weekly_avg.combine(monthly_avg, max)
        })

        par_stock.reset_index(inplace=True)

        # Add columns for frontend interaction
        par_stock["Item Code"] = ""
        par_stock["Unit"] = ""
        par_stock["Stock in Hand"] = 0
        par_stock["Expected Delivery"] = 0
        par_stock["Final Stock Needed"] = 0
        par_stock["Supplier"] = "Other"

        # Load Barakat and OFI files
        barakat_df = pd.read_excel(BytesIO(await barakat_file.read()))
        ofi_df = pd.read_excel(BytesIO(await ofi_file.read()))

        # Clean item names for matching
        def clean_name(name): return str(name).strip().lower()
        barakat_items = set(barakat_df["Item Name"].dropna().map(clean_name))
        ofi_items = set(ofi_df["Item Name"].dropna().map(clean_name))

        # Assign supplier + placeholder fields
        for idx, row in par_stock.iterrows():
            item_clean = clean_name(row["Item"])
            if item_clean in barakat_items:
                par_stock.at[idx, "Supplier"] = "Barakat"
            elif item_clean in ofi_items:
                par_stock.at[idx, "Supplier"] = "OFI"

        return JSONResponse(content=par_stock.to_dict(orient="records"))

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})