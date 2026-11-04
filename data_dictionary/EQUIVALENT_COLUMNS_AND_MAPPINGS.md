# Cross-Card Equivalent Columns and Domain Mapping Dictionary
**Scope**: VISA (29 cols, 154,567 rows) | PineLabs (68 cols, 48,740 rows) | Vegapay (61 cols, 1,288 rows)  
**Target Goal**: Support Task 1 (TMS-ATM Alert Detection) and Unified Cross-Card Data Harmonization.

---

## 1. Cross-Card Equivalent Columns Matrix

The following table aligns identical business concepts across all three card providers based on comprehensive analysis of real transaction datasets:

| Business Concept | VISA (29 cols) | PineLabs (68 cols) | Vegapay (61 cols) | Equivalent Meaning & Implementation Notes |
|---|---|---|---|---|
| **Merchant Category Code (MCC)** | `spmcat` | `mcc` | `MCC` | Standard 4-digit ISO 18245 MCC code. In PineLabs, code is prefixed to description (e.g., `6011-Member Financial...`). Vegapay stores code in `MCC` and narrative in `MCC Description`. |
| **MCC Description** | *(Derived / N/A)* | Embedded in `mcc` | `MCC Description` | Descriptive category label. VISA does not supply a separate MCC description. |
| **Business / Value Date** | `spbusd` | `Value Date` | `Business Date` | The batch ledger / business processing date. VISA is ISO `YYYY-MM-DD`, PineLabs is `DD/MM/YYYY HH:MM:SS`, Vegapay is ISO `YYYY-MM-DD`. Primary date for daily monitoring. |
| **Transaction Date** | `spdate` | `Transaction Date` | `Transaction Date` | Date when transaction occurred at POS/ATM. VISA is `DDMMYYYY` (needs 8-digit padding if leading zero dropped), PineLabs is `DD/MM/YYYY HH:MM:SS`, Vegapay is `DD-MM-YYYY`. |
| **Transaction Time** | `sptime` | *(In `Transaction Date`)* | `Transaction Time` | Time of transaction. VISA is `HHMMSS`, PineLabs is embedded timestamp, Vegapay is `HH:MM:SS`. Vegapay also supplies `Mastercard Time`. |
| **Settlement Date** | *(Mapped to `spbusd`)* | `Settlement Date` | `Settlement Date` | Network clearing finalization date. In PineLabs, often `'-'`. In Vegapay, ISO `YYYY-MM-DD`. |
| **Customer / Account ID** | `spacct` | `Wallet Number` | `Account Number` / `Customer ID` | **Primary key identifying a unique individual cardholder**. VISA uses `P`-prefixed account (e.g., `P000000000000866990`). PineLabs uses customer wallet account (e.g., `201202XXXXXX4022`). Vegapay provides 16-digit `Account Number` and `Customer ID`. |
| **Internal Account UUID** | `spczid` | `Card Pack Id` / `CBS Transaction ID` | `AccountId` | Internal core-banking identifier or UUID. Vegapay supplies standard UUID `AccountId`. |
| **Customer / Cardholder Name** | `spname` | *(None / `Agency Name`)* | `Card Holder Name` | Cardholder legal full name. PineLabs does not expose individual cardholder names in the spend feed. |
| **Card Number (Masked PAN)** | `spcard` | `Device Number` | `Card Number` | Masked card number (e.g., `436733******1552`, `541778XXXXXX5038`, `******0671`). |
| **Card Proxy / Secondary ID** | *(None)* | `Device Number Alias` | `Card proxy Id` | Physical proxy or device alias. |
| **Customer Classification** | `spctyp` | `Product Type` | `Cardholder Type` | Retail, Corporate, Prepaid classification. |
| **Corporate / Company Name** | `spcnam` | `Corporate Name` | `Corporate Name` | Company name for commercial/corporate card programs. Blank for retail users. |
| **Transaction Amount** | `SPTRN$` | `Transaction Amount` | `Transaction Amount` | Numerical amount in the original currency presented at the terminal. |
| **Transaction Currency** | `sptrcc` | `Transaction Currency` | `Transaction Currency` | ISO 4217 3-letter currency code (e.g., USD, GBP, EUR, AED, KRW). |
| **USD Equivalent Amount** | `spmusa` | `Billing Amount` (when USD) | `Billing Amount` (when USD) | **Essential for Task 1 ($1500 USD threshold)**. In VISA, `spmusa` is the exact spend merchant settlement amount in USD across all foreign currencies. In PineLabs and Vegapay, `Billing Amount` is in USD for USD-billed forex cards. |
| **Billing Amount** | `spptam` | `Billing Amount` | `Billing Amount` | Amount billed to cardholder account/wallet. |
| **Billing Currency** | `sppucc` | `Billing Currency` | `Billing Currency` | Currency of cardholder account/wallet. |
| **Settlement Amount** | `spmusa` / `spptam` | `Settlement Amount` | `Settlement Amount` | Amount settled between acquirer and issuer through card network. |
| **Settlement Currency** | `sppucc` | `Settlement Currency` | `Settlement Currency` | Currency used for interchange settlement. |
| **Debit / Credit Indicator** | `spdbcr` | `DR/CR to Cardholder` | `Dr/Cr` | `DB` / `DR` for debit transactions; `CR` for credits / refunds. |
| **Transaction Type / Status** | `sptdes` | `Transaction Type` | `Transaction Description` | Human-readable narrative: `MERCHANT PURCHASE`, `Cash Withdrawal`, `Transaction Successful`. |
| **Transaction Code** | *(None)* | `Transaction Code` | `Transaction Code` | Numeric or short code: PineLabs `01` (Purchase), `04` (Cash Withdrawal), `ST` (Tax); Vegapay `00` (Purchase). |
| **Merchant Name & Location** | `spldes` | `Merchant Name & Location` | `Merchant Name` + `Merchant City` | Merchant vendor descriptor. Vegapay separates city and country into individual columns. |
| **Merchant Country Code** | Extracted from `spldes` | Extracted / `State/Province` | `Merchant Country` | 2-letter ISO country code. Vegapay explicitly stores `Merchant Country` (e.g., `GB`, `US`, `IN`). |
| **Terminal ID** | `spcati` | `Terminal ID` | `Terminal ID` | Physical terminal identifier (usually 8 digits, requiring zero padding if stripped). |
| **Card Acceptor ID** | `spcaid` | `Card Acceptor ID` | `Mer Code` | Acquirer Merchant ID / Card Acceptor identifier. |
| **System Trace Audit No (STAN)** | `spstan` | `Trace Audit Number` | `RRN` | Trace number for routing and dispute management. |
| **Acquirer Reference No (ARN)** | *(None)* | `arn` | `ARN` | Acquirer network interchange reference number. |
| **Authorization Code** | *(None)* | `Authorization Number` | `Authorization Number` | Network authorization approval reference. |
| **Reversal Flag** | *(None)* | `Reversal Flag` | `Reversal Flag` | Indicates original transaction vs charge reversal. |
| **Fees & Markups** | `spfeam`, `spmrkp` | `Markup Fee`, `Transaction Fees` | `Posted Markup Fee`, `Cash Withdrawal fee` | Itemized cardholder fees. |
| **Tax on Fees (GST)** | `spfgst`, `spmgst` | `Tax Amount` | `Posted Fee GST`, `Posted Markup Fee GST` | Tax assessed on fees. |
| **Source File Name** | `source_file` | `source_file` | `source_file` | File batch name where record was originally ingested. |

---

## 2. Segregated Domain Classification

To maintain high data governance, customer privacy (PII), and separation of concerns, all columns across the three datasets are partitioned into four discrete functional domains:

### Domain 1: Customer & Individual Details (PII & Identity)
Columns in this domain identify the cardholder, customer entity, card instrument, and KYC profile. **Access should be restricted and masked in non-administrative logs.**

* **VISA**:
  - `spacct`: Unique Customer Account ID (e.g., `P000000000000866990`)
  - `spname`: Cardholder Full Legal Name (e.g., `SUNDARAM RAJKUMAR`)
  - `spcard`: Masked Primary Account Number (PAN) (e.g., `436733******1552`)
  - `spczid`: Client / Customer Reference ID
  - `spctyp`: Cardholder Type (`Retail`)
  - `spcnam`: Corporate Name (blank if retail)
* **PineLabs**:
  - `Wallet Number`: Unique Customer Wallet / Account ID (e.g., `201202XXXXXX4022`)
  - `Device Number`: Masked Device / Card PAN (e.g., `541778XXXXXX5038`)
  - `Device Number Alias`: Secondary device identifier
  - `Virtual Card Number`: Virtual PAN token
  - `Corporate Name` & `Corporate Id`: Corporate sponsor details
  - `Agent Entity Name`, `Branch Entity ID`, `Branch Entity Name`, `Agency Name`: Issuing channel partner details
  - `Product Type`: Prepaid / Retail product type
* **Vegapay**:
  - `Account Number`: 16-digit primary cardholder account number (e.g., `1000000000000304`)
  - `Customer ID`: 16-digit core banking customer identifier (e.g., `3671788600389206`)
  - `AccountId`: Internal customer account UUID
  - `Card Holder Name`: Legal name of the cardholder (e.g., `VIKRAM GUTTHI`)
  - `Card Number`: Masked card PAN (e.g., `******0671`)
  - `Card proxy Id`: Physical proxy token identifier
  - `DOB`: Date of Birth (**Critical PII - KYC**)
  - `Passport Number`: Passport Document ID (**Critical PII - KYC**)
  - `Cardholder Type`: Retail / Corporate flag
  - `Corporate Name`: Corporate entity name

---

### Domain 2: Main Transaction Data (Financials, Dates & Status)
Columns that record the financial debit/credit event, amounts, currencies, exchange conversions, fees, timestamps, and execution status.

* **VISA**:
  - `spbusd`: Business / Accounting Date (`YYYY-MM-DD`)
  - `spdate` & `sptime`: Transaction Date (`DDMMYYYY`) & Time (`HHMMSS`)
  - `SPTRN$`: Transaction Amount in transaction currency
  - `sptrcc`: Transaction Currency Code
  - `spdbcr`: Debit/Credit indicator (`DB` / `CR`)
  - `sppucc`: Posted Currency Code
  - `sputa`: Transaction Amount in posted currency
  - `spptam`: Total Posted Amount billed
  - `spmusa`: Settlement / Spend Merchant USD Equivalent Amount
  - `spfeam` & `spfgst`: Base fee and fee GST
  - `spmrkp` & `spmgst`: Currency markup and markup GST
  - `sptdes`: Transaction status narrative
* **PineLabs**:
  - `Value Date`: Business Date (`DD/MM/YYYY HH:MM:SS`)
  - `Transaction Date`: Transaction Timestamp (`DD/MM/YYYY HH:MM:SS`)
  - `Settlement Date`: Settlement completion date
  - `Transaction Amount` & `Transaction Currency`: Original transaction amount and ISO currency
  - `Billing Amount` & `Billing Currency`: Amount billed to cardholder (USD for international forex)
  - `Settlement Amount` & `Settlement Currency`: Interbank settlement amount and currency
  - `Conversion Rate`: FX exchange rate applied
  - `DR/CR to Cardholder`: Debit or credit balance effect
  - `Transaction Code` & `Transaction Type`: E.g., `01` (Purchase), `04` (Cash Withdrawal), `ST` (Tax)
  - `Markup Fee`, `Transaction Fees`, `Tax Amount`, `Total Fees & Charges`: Itemized fees and GST
  - `DCC Pre-Conversion Amount` & `DCC Pre-Conversion Currency`: Dynamic currency conversion info
  - `Cashback Amount` & `Cashback Currency`: Loyalty/cashback rewards
  - `Reversal Flag` & `Partial Approval`: Transaction lifecycle status
* **Vegapay**:
  - `Business Date`: Business accounting date (`YYYY-MM-DD`)
  - `Transaction Date` & `Transaction Time`: Terminal transaction date and time
  - `Mastercard Date` & `Mastercard Time`: Network clearing date and time
  - `Settlement Date` & `Settlement Time`: Final settlement date and timestamp
  - `Transaction Amount` & `Transaction Currency`: Original transaction amount and ISO currency
  - `Billing Amount` & `Billing Currency`: Amount billed to customer (USD for international forex)
  - `Settlement Amount` & `Settlement Currency`: Settlement amount and currency
  - `Posted Wallet Currency` & `Posted Transaction Wallet Amount`: Wallet ledger amount
  - `Total CPF Posted Wallet Amount`: Total cardholder processing fee
  - `Dr/Cr`: Debit/Credit indicator (`DR` / `CR`)
  - `Posted Fee Amount`, `Posted Fee GST`, `Posted Markup Fee`, `Posted Markup Fee GST`: Itemized fee components
  - `Cash Withdrawal fee` & `Cash Withdrawal Fee GST`: Dedicated ATM cash fees
  - `Balance Enquiry Fee` & `Balance Enquiry Fee GST`: Dedicated ATM balance inquiry fees
  - `Transaction Code` & `Transaction Code Narration`: `00` (PURCHASE), `01` (CASH), etc.
  - `Transaction Description` & `Decline Reason`: Status narrative and error code
  - `Days count`: Interest / settlement day counter

---

### Domain 3: Merchant & Acceptance Details
Columns defining the merchant acceptor, industry classification code (MCC), point-of-sale terminal, and geographic location.

* **VISA**:
  - `spmcat`: Merchant Category Code (4 digits, e.g., `6011`, `5812`)
  - `spldes`: Merchant Name and Location narrative (e.g., `CHOPSTIX BEACONSFIELD GB`)
  - `spcaid`: Card Acceptor ID / Merchant ID
  - `spcati`: Card Acceptor Terminal ID (padded 8-digit string)
  - `spbin` & `spdesc`: BIN identifier and program description
* **PineLabs**:
  - `mcc`: Merchant Category Code with embedded narrative (e.g., `6011-Member Financial Institution Automated Cash Disbursements`)
  - `Merchant Name & Location`: Merchant narrative string
  - `Card Acceptor ID`: Merchant ID
  - `Terminal ID`: Terminal identifier (8 digits)
  - `channel`: `Customer Portal`, `E-Commerce`, `POS`
  - `Transaction Origin`: `Domestic` or `International`
  - `State/Province`: Merchant state/region
  - `ECOMM Indicator` & `UCAF Indicator`: E-commerce flags
* **Vegapay**:
  - `MCC`: 4-digit numeric MCC code (e.g., `6011`)
  - `MCC Description`: Dedicated description string (e.g., `Bakeries`, `Member Financial Institution...`)
  - `Merchant Name`: Vendor name
  - `Merchant City`: Terminal city
  - `Merchant Country`: ISO 2-letter country code (e.g., `GB`, `US`, `IN`)
  - `Mer Code`: 15-digit Merchant Acquirer Code
  - `Terminal ID`: 8-digit terminal identifier
  - `Transaction Type`: Device category (`POS`, `ATM`, `ECOM`)

---

### Domain 4: Clearing, Network Audit & Trace Details
Columns used for network tracing, interchange settlement reconciliation, chargeback dispute handling, and batch feed tracking.

* **VISA**:
  - `spstan`: System Trace Audit Number (STAN)
  - `source_file`: Ingestion batch file name
* **PineLabs**:
  - `arn`: Acquirer Reference Number (ARN)
  - `Authorization Number`: Issuer authorization code
  - `Trace Audit Number`: System Trace Audit Number (STAN)
  - `CBS Transaction ID`: Core Banking System identifier
  - `Reference Number`: Network transaction reference
  - `MultiClearing Indicator`, `MultiClearing Total Amount`, `MultiClearing Seq No`, `MultiClearing Seq Count`
  - `source_file`: Ingestion batch file name
* **Vegapay**:
  - `Transaction Id`: Unique transaction UUID
  - `Transaction Number`: Sequential account transaction index
  - `ARN`: 23-digit Acquirer Reference Number
  - `Authorization Number`: 6-character auth approval code
  - `RRN`: 12-digit Retrieval Reference Number (STAN equivalent)
  - `MultiClearing Indicator`: Part-settlement indicator
  - `ISIC Serial Number`: Industrial classification code
  - `source_file`: Ingestion batch file name

---

## 3. Deep-Dive on Key Analytical Fields for Task 1

### A. Merchant Category Code (MCC) Comparison
Task 1 requires filtering for High-Risk ATM MCCs:
* `6011`: Automated Cash Disbursements (ATMs)
* `6010`: Manual Cash Disbursements (Bank tellers / branches)
* `6050`: Quasi-Cash / Merchant Financial Institutions
* `6051`: Non-Financial Institutions – Foreign Currency, Money Orders, Crypto

| Card Provider | Storage Pattern | Filtering Mechanism (SQL & Python) |
|---|---|---|
| **VISA** | Clean 4-digit string in `spmcat` (e.g. `'6011'`). | `spmcat IN ('6011', '6010', '6050', '6051')` |
| **PineLabs** | String with hyphen: `'6011-Member Financial Institution...'`. Also contains `'-'` for tax rows. | `LEFT(mcc, 4) IN ('6011', '6010', '6050', '6051')` |
| **Vegapay** | Clean 4-digit code in `MCC` (e.g. `'6011'`). Description is kept in `MCC Description`. | `CAST(MCC AS VARCHAR(10)) IN ('6011', '6010', '6050', '6051')` |

### B. Individual Identification Strategy
* **VISA**: Group by `spacct` (Customer Account ID). Cardholder name `spname` is joined for reporting.
* **PineLabs**: Group by `Wallet Number`. PineLabs does not expose legal cardholder names in this feed; `Wallet Number` represents the individual customer's central account.
* **Vegapay**: Group by `Account Number` (or `Customer ID`). Cardholder name `Card Holder Name` is joined for reporting.

### C. USD Equivalent Calculation Strategy
Task 1 evaluates whether total volume on ATM transactions exceeds **$1,500 USD**:
* **VISA**: `spmusa` is the exact spend merchant settlement amount in USD calculated by Visa at conversion time.
* **PineLabs**: For 92% of ATM transactions, `Billing Currency == 'USD'` and `Billing Amount` is the exact USD debit. For non-USD billing (e.g. GBP cards), `Settlement Amount` or `Billing Amount * Conversion Rate` represents the normalized amount.
* **Vegapay**: When `Billing Currency == 'USD'`, `Billing Amount` is used. When card is billed in GBP/EUR, `Billing Amount` represents the primary wallet currency.

---
*Created automatically from 100% data read across VISA, PineLabs, and Vegapay source feeds.*
