# Inventory Stock Tracker
An individual Python for Machine Learning (BTA30104) project for an electronics and computer shop. This local Flask web app stores inventory and transactions in MySQL. Start here after extracting the ZIP.

## 1. Prepare MySQL
Install Python 3.10 or later and MySQL Server 8.0 or later. Start the MySQL service and open MySQL Workbench (or the mysql client) as a database administrator. Run the following once, replacing the example password with a password of your choice. The commands create a dedicated application database and user.

~~~sql
CREATE DATABASE stock_tracker CHARACTER SET utf8mb4;
CREATE USER 'stock_app'@'127.0.0.1' IDENTIFIED BY 'choose-a-database-password';
GRANT SELECT, INSERT, UPDATE, CREATE, REFERENCES ON stock_tracker.* TO 'stock_app'@'127.0.0.1';
~~~

## 2. Install and configure
Open a terminal in the extracted InventoryStockTracker folder, alongside app.py and requirements.txt.

**macOS**
~~~sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
~~~

**Windows PowerShell**
~~~powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
~~~

Edit .env in a text editor. Set MYSQL_PASSWORD to the database password you chose. Keep MYSQL_HOST=127.0.0.1 for the local setup. If your password contains spaces or #, quote its value. Keep your .env and instance/session.key private. The app generates the session key at first launch.

## 3. Start the web app
On macOS with the virtual environment active:

~~~sh
python -m flask --app app setup --demo
python -m flask --app app run --port 5050
~~~

On Windows PowerShell:

~~~powershell
.\.venv\Scripts\python.exe -m flask --app app setup --demo
.\.venv\Scripts\python.exe -m flask --app app run --port 5050
~~~

Choose a password for the web administrator when prompted. Open http://127.0.0.1:5050 and sign in as **admin** with this password. The setup command prints the generated passwords for the sample buyer and supplier when it creates them. Setup preserves existing products and quantities when rerun. Omit --demo for an empty catalogue. For subsequent sessions, only the run command is needed. Stop the local server with Ctrl+C.

## Demonstrate the assignment in three minutes
1. Search Inventory for SSD-512. Its opening stock is 12 and its threshold is 5 in a fresh demo. The warehouse map shows it in aisle 1, bin 1 with the USB drive.
2. Open Record movement, select Sale, choose SSD-512 and the Campus IT Lab buyer. Sell 7 units at the default price. The receipt shows a closing balance of 5, and the product enters the reorder watchlist.
3. Try selling 6 more. The app reports that only 5 are available. The rejected sale creates no receipt.
4. Record a Purchase of 4 units from Eastern Components. Stock rises to 9 and the warning clears. View History or export the inventory CSV.
5. To demonstrate a return, choose Customer return, select SSD-512 and enter 1 unit plus the original sale receipt number. The product returns to stock, and the return links to the sale.

## How Python meets the brief
inventory.py builds Warehouse. The outer list represents aisles, the inner list holds bins, and each bin contains product dictionaries. Multiple products can share a bin. For example, warehouse.aisles[0][0] contains aisle 1, bin 1. The by_code dictionary points to the same product dictionaries. The inventory search tries an exact dictionary lookup before text filtering. The web app rebuilds this view from committed MySQL records for each inventory request. One SKU has one assigned location.

closing_quantity calculates stock changes. status returns Out of stock at zero, Low stock at or below the item's threshold, and In stock above it. Each posting locks the product row, validates the change, then saves the balance and receipt in one transaction. Repeated submissions carrying the same form ticket reuse the receipt.

## Accounts and billing
- Admin manages products, staff and trading accounts, transactions and count corrections. Stock counts use the new absolute quantity and require a reason.
- Staff manage products, create buyers and suppliers, record purchases, sales and linked returns, and export data.
- Buyers and suppliers sign in to view, print and export their own transactions. Staff record transactions on their behalf.
- A receipt covers one SKU. Enter a unit price or accept the catalogue price. Discount is applied before the optional tax percentage. Amounts are in INR and rounded to paise. The print button uses the browser print dialog, which can also save a PDF.
- Returns inherit pricing, discount and tax from the original receipt. Cumulative returns cannot exceed its quantity. Credit amounts are rounded per receipt.
- Stock valuation uses current catalogue cost. Catalogue prices are maintained on the product page. A USB barcode scanner configured as a keyboard can enter product codes into the inventory search field.

## Check the project
Run the six stand-alone unit tests with your Python interpreter:

~~~sh
python -m unittest discover -s tests
~~~

For an end-to-end check, run setup --demo in a **disposable demo database**, then use the following command. It uses Flask's test client with the configured MySQL connection and asks for the administrator password. It creates a clearly marked test SKU and keeps its history. On Windows replace python with .\.venv\Scripts\python.exe.

~~~sh
python -m tests.mysql_smoke
~~~

If the app reports a database connection failure, check the running MySQL service, host, port and database credentials in .env. An unknown-table error usually means the setup command has yet to run.

## Deploy this repository on Railway
Use the repository root as the app service's source. The included railway.toml starts Gunicorn and initializes missing tables and sample records. For an existing deployment, keep the existing MySQL service, database and session secret. Pushing to GitHub alone does not link this repository to the running service.

Configure these on the web service under Variables (the references below assume the database service is named MySQL):

    MYSQL_HOST=${{MySQL.MYSQLHOST}}
    MYSQL_PORT=${{MySQL.MYSQLPORT}}
    MYSQL_USER=${{MySQL.MYSQLUSER}}
    MYSQL_PASSWORD=${{MySQL.MYSQLPASSWORD}}
    MYSQL_DATABASE=${{MySQL.MYSQLDATABASE}}

Set SESSION_SECRET to a persistent random value and INITIAL_ADMIN_PASSWORD to a private password of 8–128 characters for the first admin account. The latter is used only when the database contains no administrator. Railway supplies PORT. Hosted startup suppresses demo-account passwords in logs. Configure new buyer or supplier accounts through the admin dashboard.
