# Qatar bank transactions: data structure

46 fields, merged from both images (rows 1–23 and 22–46). One record per row.

| # | Field | Type | Sample value | Synthetic rule |
|---|---|---|---|---|
| 1 | BOOKING_DATE | Date | 8/1/2022 | Transaction booking date, spread over a 12-month window |
| 2 | STMT_ENTRY_ID | Text (15-digit number) | 1.9936E+14 (e.g. 199360000000000) | Unique statement entry ID; stored as text so Excel does not show it in scientific notation |
| 3 | TRANSACTION_CODE | Integer | 335 | Code tied to the transaction type (e.g. 335 utility payment, others for transfers, salaries, trade) |
| 4 | AMOUNT_LCY | Decimal(18,2) | 30 | Amount in QAR; realistic ranges per transaction type |
| 5 | CURRENCY | Char(3) | QAR | Mostly QAR, some USD/EUR/AED |
| 6 | CUSTOMER_ID | Text (masked) | DxMQMQI | Bank's own customer ID, stable per company |
| 7 | CUSTOMER_NAME | Text | Ooredoo QPSC | Real Qatar company (bank's customer) |
| 8 | DEBIT_CREDIT_IND | Char(1): C / D | C | C = money in, D = money out |
| 9 | CHANNEL_TYPE | Text | Mobile Banking | Mobile Banking, Internet Banking, Branch, Host-to-Host, SWIFT |
| 10 | TXN_CLASSIFICATION | Text | Utility Payment | Utility Payment, Supplier Payment, Salary, Trade Finance, Intercompany, Rent, etc. |
| 11 | TXN_SUB_CLASSIFICATION | Text | Ooredoo Q.P.S.C | Finer category, often the biller or counterparty |
| 12 | TRANSACTION_CHANNEL | Text | FUNDS_TRANSFER | FUNDS_TRANSFER, BILL_PAYMENT, CHEQUE, SWIFT, WPS |
| 13 | PURPOSE_DESC | Text, nullable | NULL | Payment purpose or NULL |
| 14 | O_IBAN_NUMBER | Text (29-char Qatar IBAN) | QA75QISBDxOUYYMQMQIYYWYYYYYYYYY | Own-side (customer) IBAN: QA + 2 check digits + 4-letter bank code + 21 chars |
| 15 | O_BANK_CD | Integer | 4 | Own bank code |
| 16 | CP_ACCOUNT_NUMBER | Text (masked) | DxWWYYQOGQOWWWYYYYYYYYY | Counterparty account number |
| 17 | CP_CUSTOMER_NAME | Text | FARRUKH JAMALUDDIN | Counterparty name: a real Qatar company |
| 18 | CP_BANK_CD | Integer | 4 | Counterparty bank code (same bank or one of the other Qatar banks) |
| 19 | CP_IBAN_NUMBER | Text (29-char Qatar IBAN) | QA60QISBDxWWYYQOGQOWWWYYYYYYYYY | Counterparty IBAN, bank code matches CP_BANK_CD |
| 20 | CP_CURRENCY | Char(3) | QAR | Counterparty account currency |
| 21 | O_PART_IBAN | Text | QISBDxOUYYMQMQIYYWYYYYY | O_IBAN_NUMBER without 'QA' + check digits |
| 22 | CP_PART_IBAN | Text | QISBDxWWYYQOGQOWWWYYYYYYYYY | CP_IBAN_NUMBER without 'QA' + check digits |
| 23 | CHANNEL_ID | Text code | OMB | Short code for CHANNEL_TYPE (OMB, IB, BR, H2H, SWF) |
| 24 | QIB_RATING | Integer | 2 | Customer internal risk rating (1–10) |
| 25 | UNIQUE_ID | Text | C_DxQOGQOWW | 'C_' + counterparty key; one stable ID per counterparty (this is the node ID for the graph) |
| 26 | MATCH_CIF_ID | Text, nullable | NULL | Bank CIF of the counterparty if it is also a customer, else NULL |
| 27 | PROSPECT_NAME | Text | FARRUKH JAMALUDDIN | Counterparty name when it is a prospect (not a customer) |
| 28 | TRANSACTION_TYPE | Text code | ACUT | Core-banking transaction type code (ACUT, ACOT, ACSA, ACCQ, etc.) |
| 29 | TXN_INITIATED | YES / NO | YES | Whether the customer initiated the transaction |
| 30 | ACCOUNT_OFFICER | Integer | 6112 | Relationship manager code, stable per customer |
| 31 | ACCOUNT_OFFICER_NAME | Text | Mohamed Rajab | Relationship manager name (fictional) |
| 32 | SECTOR | Integer | 701 | Sector code |
| 33 | SECTOR_NAME | Text | Corp 1 - Govt and Related Entities | Sector segment of the customer |
| 34 | INDUSTRY | Integer | 4205 | Industry code |
| 35 | INDUSTRY_NAME | Text | Telecommunication | Customer industry (Energy, Banking, Real Estate, Telecom, Construction, etc.) |
| 36 | VINTAGE | Date | 1/30/1992 | Date the customer relationship started |
| 37 | BUSINESS_UNIT | Text | Corp I - GRE | Business unit |
| 38 | BUSINESS_GROUP | Text | WBG | Business group (WBG = Wholesale Banking Group) |
| 39 | BANK_NAME | Text | Qatar Islamic Bank | Name of the reporting bank |
| 40 | PROSPECT_ID | Text, nullable | NULL | Prospect ID or NULL |
| 41 | BOOKING_DATE_SK | Integer (YYYYMMDD) | 20220801 | Derived from BOOKING_DATE |
| 42 | BOOKING_MONTH_SK | Integer (YYYYMM) | 202208 | Derived from BOOKING_DATE |
| 43 | BATCH_DATE | Date | 9/7/2022 | Load date of the batch, after the booking date |
| 44 | COMPANY_FLAG | Text, nullable | NULL | Flag or NULL |
| 45 | AMOUNT_FCY | Decimal, nullable | (cut off in image, looks NULL) | Foreign-currency amount when CURRENCY is not QAR, else NULL  [inferred] |
| 46 | OUR_REFERENCE | Text | (name only, in formula bar) | Bank transaction reference, e.g. FT22213XXXXX  [inferred] |
