<!DOCTYPE html>
<html>
<head>
  <title>Par Stock Calculator</title>
  <style>
    body { font-family: Arial; margin: 20px; }
    table, th, td { border: 1px solid black; border-collapse: collapse; padding: 5px; }
    th { background-color: #f2f2f2; }
    input[type="file"] { margin-bottom: 10px; }
    button { margin: 5px; }
  </style>
</head>
<body>

<h2>Upload Weekly & Monthly Excel Files</h2>

<input type="file" id="monthlyFile" /> Monthly consumption.xlsx<br/>
<input type="file" id="weeklyFile" /> Weekly Consumption.xlsx<br/>
<input type="file" id="supplierFile" /> Upload Supplier File<br/>

<br/>
<button onclick="calculateParStock()">Calculate Par Stock</button>

<h3>Search:</h3>
<input type="text" id="searchInput" placeholder="Search for item..." onkeyup="searchTable()" />
<div id="supplierButtons"></div>
<button onclick="exportToCSV()">Export as CSV</button>

<br/><br/>
<table id="stockTable">
  <thead>
    <tr>
      <th>Item</th>
      <th>Item Code</th>
      <th>Unit</th>
      <th>Suggested Par</th>
      <th>Stock in Hand</th>
      <th>Final Stock Needed</th>
      <th>Supplier</th>
    </tr>
  </thead>
  <tbody>
    <!-- Filled by JS -->
  </tbody>
</table>

<script>
let supplierList = [];

function searchTable() {
  const input = document.getElementById("searchInput").value.toLowerCase();
  const rows = document.querySelectorAll("#stockTable tbody tr");
  rows.forEach(row => {
    row.style.display = row.innerText.toLowerCase().includes(input) ? "" : "none";
  });
}

function exportToCSV() {
  // implement as per your CSV logic
}

function calculateParStock() {
  alert("Pretend we calculated and populated the table. 😊 Now filter buttons work!");
  populateSampleData(); // for demo
}

function populateSampleData() {
  const data = [
    { item: "Hummus", code: "RM-10001", unit: "KG", par: 50, stock: 20, supplier: "Barakat" },
    { item: "Butter", code: "RM-10002", unit: "KG", par: 80, stock: 40, supplier: "OFI" },
    { item: "Garlic Paste", code: "RM-10003", unit: "L", par: 20, stock: 30, supplier: "OFI" },
  ];

  const tbody = document.querySelector("#stockTable tbody");
  tbody.innerHTML = "";
  data.forEach(d => {
    const final = Math.max(0, d.par - d.stock);
    const row = `<tr data-supplier="${d.supplier}">
      <td>${d.item}</td>
      <td>${d.code}</td>
      <td>${d.unit}</td>
      <td>${d.par}</td>
      <td>${d.stock}</td>
      <td>${final}</td>
      <td>${d.supplier}</td>
    </tr>`;
    tbody.innerHTML += row;
  });

  createSupplierButtons(["Barakat", "OFI"]);
}

function createSupplierButtons(suppliers) {
  const container = document.getElementById("supplierButtons");
  container.innerHTML = "";
  suppliers.forEach(s => {
    const btn = document.createElement("button");
    btn.textContent = s;
    btn.onclick = () => filterBySupplier(s);
    container.appendChild(btn);
  });

  const showAllBtn = document.createElement("button");
  showAllBtn.textContent = "Show All";
  showAllBtn.onclick = () => filterBySupplier("all");
  container.appendChild(showAllBtn);
}

function filterBySupplier(supplier) {
  const rows = document.querySelectorAll("#stockTable tbody tr");
  rows.forEach(row => {
    const currentSupplier = row.getAttribute("data-supplier").toLowerCase();
    row.style.display = (supplier === "all" || currentSupplier === supplier.toLowerCase()) ? "" : "none";
  });
}
</script>

</body>
</html>