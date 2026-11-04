# Vegapay Data Dictionary

**Source Dataset**: `Vegapay` feed (1,288 total rows analyzed)
**Analysis Scope**: 100% of rows analyzed across data types, null rates, cardinality, and formats.

| # | Column Name | Business Description | Storage Type & Format | Null Rate | Distinct Values | Sample Non-Null Values |
|---|---|---|---|---|---|---|
| 1 | **`Business Date`** | Business / processing date for the transaction batch | Business Date (ISO YYYY-MM-DD) | 0.0% | 29 | `2026-10-12`, `2026-10-02`, `2026-10-01` |
| 2 | **`Customer ID`** | Unique persistent customer identifier in core system | Customer ID (16-digit numeric string) | 0.0% | 80 | `3671788600389206`, `4431783505714124`, `2771784544162441` |
| 3 | **`BIN`** | Bank Identification Number for card product range | BIN (8-digit numeric string) | 0.0% | 1 | `22352632` |
| 4 | **`Product Description`** | Card program product description | Product Description (Text) | 0.0% | 1 | `Forex Ebix Program` |
| 5 | **`AccountId`** | Internal UUID account identifier | Account UUID (36-char string) | 0.0% | 80 | `01a070fb-12c5-754b-b0de-46da4c8578ad`, `019f415e-760f-7bd0-a326-3c46171c37a6`, `019f7f3c-a798-7797-bb86-40353d30a2ce` |
| 6 | **`Account Number`** | Primary cardholder customer account number | Account Number (16-digit numeric string) | 0.0% | 80 | `1000000000000304`, `1000000000000216`, `1000000000000225` |
| 7 | **`Transaction Number`** | Sequential transaction number in account ledger | Txn Number (16-digit numeric string) | 0.0% | 1,286 | `1000000000009287`, `1000000000008106`, `1000000000008059` |
| 8 | **`Card Holder Name`** | Full legal name of the cardholder | Cardholder Name (Upper-case text) | 0.0% | 80 | `VIKRAM GUTTHI`, `AAYUSHI PATEL`, `VINITKUMAR KHALASI` |
| 9 | **`DOB`** | Cardholder date of birth (KYC PII) | Date of Birth (DD-MM-YYYY) | 0.0% | 73 | `31-12-2000`, `20-02-1999`, `13-07-2004` |
| 10 | **`Passport Number`** | Cardholder passport number (KYC PII) | Passport Number (Alphanumeric string) | 0.0% | 80 | `B6887966`, `R4576029`, `C3408494` |
| 11 | **`Cardholder Type`** | Classification of cardholder (e.g. RETAIL, CORPORATE) | Cardholder Type (Text) | 0.0% | 1 | `RETAIL` |
| 12 | **`Corporate Name`** | Name of corporate entity for corporate programs | Corporate Name (Text) | 0.0% | 1 | `EBIX` |
| 13 | **`Card Number`** | Masked card PAN number | Masked PAN (e.g. ******0671) | 0.0% | 80 | `******0671`, `******1998`, `******3469` |
| 14 | **`Card proxy Id`** | Proxy identifier mapping to physical card | Card Proxy ID (12-digit numeric string) | 0.0% | 80 | `108910033895`, `108910002588`, `108910003085` |
| 15 | **`MCC`** | Merchant Category Code classifying vendor | MCC Code (4-digit numeric string) | 0.0% | 77 | `5462`, `5499`, `4111` |
| 16 | **`MCC Description`** | Standard description of Merchant Category Code | MCC Description (Text) | 0.62% | 76 | `Bakeries`, `Miscellaneous Food Stores-Convenience Stores, Markets, Specialty Stores, and Vending Machines`, `Transportation?Suburban and Local Commuter Passenger, including Ferries` |
| 17 | **`Mastercard Date`** | Transaction date recorded by Mastercard network | Mastercard Date (DD-MM-YYYY) | 0.08% | 32 | `10-10-2026`, `30-09-2026`, `29-09-2026` |
| 18 | **`Mastercard Time`** | Transaction time recorded by Mastercard network | Mastercard Time (HH:MM:SS) | 0.08% | 1,270 | `13:02:13`, `14:38:06`, `06:45:20` |
| 19 | **`Days count`** | Days elapsed count for settlement calculation | Days Count (Signed integer/float) | 0.08% | 4 | `-1.0`, `0.0`, `-2.0` |
| 20 | **`Transaction Amount`** | Amount in original currency of transaction | Txn Amount (Decimal numeric) | 0.0% | 642 | `4.0`, `10.75`, `5.25` |
| 21 | **`Transaction Currency`** | ISO currency code of original transaction | Txn Currency (ISO 3-letter alpha) | 0.0% | 13 | `GBP`, `SEK`, `AED` |
| 22 | **`Dr/Cr`** | Debit or Credit transaction indicator | DR / CR Indicator (DR / CR) | 0.0% | 1 | `DR` |
| 23 | **`Posted Wallet Currency`** | Currency of wallet balance posted against | Wallet Currency (ISO 3-letter alpha) | 0.0% | 8 | `GBP`, `EUR`, `AED` |
| 24 | **`Posted Transaction Wallet Amount`** | Amount debited/credited to wallet | Wallet Amount (Decimal numeric) | 0.0% | 656 | `4.0`, `10.75`, `5.25` |
| 25 | **`Posted Fee Amount`** | Fee amount assessed to wallet | Fee Amount (Decimal / blank) | 100.0% | 0 |  |
| 26 | **`Posted Fee GST`** | GST on posted fee | Fee GST (Decimal / blank) | 100.0% | 0 |  |
| 27 | **`Posted Markup Fee`** | Currency conversion markup fee amount | Markup Fee (Decimal numeric) | 0.0% | 1 | `0.0` |
| 28 | **`Posted Markup Fee GST`** | GST on posted markup fee | Markup GST (Decimal numeric) | 0.0% | 1 | `0.0` |
| 29 | **`Total CPF Posted Wallet Amount`** | Total Cardholder Processing Fee / wallet debit | Total Wallet Debit (Decimal numeric) | 0.0% | 657 | `4.0`, `10.75`, `5.25` |
| 30 | **`Transaction Description`** | Status description of transaction execution | Status Narrative (e.g. Transaction Successful) | 0.08% | 1 | `Transaction Successful` |
| 31 | **`Decline Reason`** | Reason narrative if transaction was declined | Decline Reason (Text / blank) | 100.0% | 0 |  |
| 32 | **`Merchant Name`** | Name of the merchant entity | Merchant Name (Text) | 0.0% | 597 | `RV News               `, `HOLLAND AND BARRETT   `, `TfL Travel Charge     ` |
| 33 | **`Long Adjustment Description`** | Detailed description for adjustments or chargebacks | Adjustment Narrative (Text / '-') | 100.0% | 0 |  |
| 34 | **`Transaction Id`** | Unique UUID transaction identifier | Txn UUID (36-char string) | 0.0% | 1,286 | `01a125e8-2989-7850-8f89-33b3fefa8802`, `01a0f2c0-57ac-7e79-a5b3-221dc63161c4`, `01a0f10f-84b4-7069-a301-c47d807da8e5` |
| 35 | **`Authorization Number`** | Issuer network authorization reference code | Auth Code (6-char alphanumeric string) | 2.41% | 1,255 | `9XLBI5`, `4VTSJM`, `YLVCZP` |
| 36 | **`Mer Code`** | Merchant acceptor identifier / terminal owner code | Merchant ID (15-digit numeric string) | 0.08% | 591 | `712120122550218`, `8920001        `, `1022701        ` |
| 37 | **`Merchant City`** | City where merchant terminal is registered | Merchant City (Text) | 0.0% | 213 | `Luton        `, `BIRMINGHAM   `, `LONDON       ` |
| 38 | **`Merchant Country`** | ISO 2-letter country code of merchant location | Merchant Country (ISO alpha-2) | 0.08% | 16 | `GB`, `SE`, `AE` |
| 39 | **`RRN`** | Retrieval Reference Number for transaction tracing | RRN (12-digit numeric string) | 0.08% | 1,285 | `628313382258.0`, `7761.0`, `8199508678.0` |
| 40 | **`Settlement Amount`** | Amount settled through network clearing | Settlement Amount (Decimal numeric) | 0.0% | 663 | `4.0`, `10.75`, `5.25` |
| 41 | **`Settlement Currency`** | Currency used for network settlement | Settlement Currency (ISO 3-letter alpha) | 0.0% | 3 | `GBP`, `USD`, `EUR` |
| 42 | **`Billing Amount`** | Amount billed to customer account (USD for forex) | Billing Amount (Decimal numeric) | 0.0% | 663 | `4.0`, `10.75`, `5.25` |
| 43 | **`Billing Currency`** | Currency in which cardholder is billed | Billing Currency (ISO 3-letter alpha) | 0.0% | 3 | `GBP`, `USD`, `EUR` |
| 44 | **`Transaction Code`** | System transaction code (00=Purchase, 01=Cash, etc.) | Txn Code (2-digit string) | 0.08% | 3 | `0.0`, `30.0`, `1.0` |
| 45 | **`Transaction Code Narration`** | Text narration of transaction code | Code Narration (e.g. PURCHASE, ATM) | 0.0% | 4 | `PURCHASE`, `BALANCE_ENQUIRY`, `CASH_WITHDRAWAL` |
| 46 | **`Terminal ID`** | Identifier of the POS or ATM terminal | Terminal ID (8-digit numeric string) | 3.42% | 747 | `84499619`, `35896604`, `01468633` |
| 47 | **`Transaction Date`** | Date transaction took place at terminal | Txn Date (DD-MM-YYYY) | 0.08% | 32 | `10-10-2026`, `30-09-2026`, `29-09-2026` |
| 48 | **`Transaction Time`** | Time transaction took place at terminal | Txn Time (HH:MM:SS) | 0.08% | 1,256 | `14:02:13`, `15:38:00`, `07:45:09` |
| 49 | **`ARN`** | Acquirer Reference Number for interchange clearing | ARN (23-digit numeric string) | 2.33% | 1,020 | `2.9130796283009322e+22`, `8.54814762748725e+22`, `8.548147627487265e+22` |
| 50 | **`MultiClearing Indicator`** | Indicator if transaction was settled in parts | MultiClearing Flag (Yes / No) | 0.0% | 2 | `No`, `Yes` |
| 51 | **`Transaction Type`** | Category of acceptance device (POS, ATM, ECOM) | Device Category (Text) | 0.0% | 5 | `POS`, `CONTACTLESS`, `ECOM` |
| 52 | **`Settlement Date`** | Date settlement was finalized | Settlement Date (ISO YYYY-MM-DD or '-') | 2.33% | 30 | `2026-10-11`, `2026-10-01`, `2026-09-30` |
| 53 | **`Settlement Time`** | Timestamp of settlement finalization | Settlement Time (Timestamp or '-') | 2.33% | 30 | `2026-10-11 00:00:00`, `2026-10-01 00:00:00`, `2026-09-30 00:00:00` |
| 54 | **`Reversal Flag`** | Indicates if transaction was reversed | Reversal Flag (Yes / No) | 0.0% | 1 | `No` |
| 55 | **`ISIC Serial Number`** | International Standard Industrial Classification code | ISIC Code (Alphanumeric / blank) | 100.0% | 0 |  |
| 56 | **`source_file`** | Source batch file name from which record was ingested | Source Filename (Text) | 0.0% | 30 | `SPEND_2026-10-11`, `SPEND_2026-10-01`, `SPEND_2026-09-30` |
| 57 | **`Balance Enquiry Fee`** | Fee assessed for ATM balance inquiry | Inquiry Fee (Decimal numeric) | 0.0% | 2 | `0.0`, `0.5` |
| 58 | **`Balance Enquiry Fee GST`** | GST on balance inquiry fee | Inquiry Fee GST (Decimal numeric) | 0.0% | 2 | `0.0`, `0.09` |
| 59 | **`Cash Withdrawal fee`** | Fee assessed for ATM cash withdrawal | Cash Fee (Decimal numeric) | 0.0% | 1 | `0` |
| 60 | **`Cash Withdrawal Fee GST`** | GST on cash withdrawal fee | Cash Fee GST (Decimal numeric) | 0.0% | 1 | `0` |
| 61 | **`program`** | Card issuing program name | Program Name (Text) | 0.0% | 1 | `Forex Ebix Program` |