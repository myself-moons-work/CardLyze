# PineLabs Data Dictionary

**Source Dataset**: `PineLabs` feed (48,740 total rows analyzed)
**Analysis Scope**: 100% of rows analyzed across data types, null rates, cardinality, and formats.

| # | Column Name | Business Description | Storage Type & Format | Null Rate | Distinct Values | Sample Non-Null Values |
|---|---|---|---|---|---|---|
| 1 | **`Product Type`** | Type of prepaid card product | Product Type (e.g. PREPAID) | 0.0% | 1 | `PREPAID` |
| 2 | **`Value Date`** | Business value / processing date for transaction | Business Date (DD/MM/YYYY HH:MM:SS) | 0.0% | 26 | `30/09/2026 00:00:00`, `28/09/2026 00:00:00`, `29/09/2026 00:00:00` |
| 3 | **`Program Name`** | Name of the issuing card program | Program Name (Text) | 0.0% | 2 | `ECDC01 EBIXCASH Dual Card Program 01`, `ECSC01 EBIXCASH Single Card Program 01` |
| 4 | **`channel`** | Origination channel (e.g. Customer Portal, E-Commerce, POS) | Channel (Text) | 0.0% | 5 | `Customer Portal`, `E-Commerce`, `POS` |
| 5 | **`Transaction Origin`** | Domestic or International transaction indicator | Origin (Domestic / International) | 0.0% | 2 | `Domestic`, `International` |
| 6 | **`Transaction Code`** | System transaction code (01=Purchase, 04=Cash Withdrawal, ST=Tax) | Txn Code (2-char code) | 0.0% | 12 | `ST`, `01`, `21` |
| 7 | **`Transaction Type`** | Descriptive narrative of transaction type | Txn Type (e.g. Cash Withdrawal, Purchase) | 0.0% | 14 | `Service Tax/Tax On Income`, `Purchase/Auth Completion`, `Card fees` |
| 8 | **`Device Type`** | Device / acceptance channel category | Device Type (Text) | 0.0% | 1 | `4 NFC Device - EMV Paypass` |
| 9 | **`Device Number`** | Masked card / device number | Masked PAN (e.g. 541778XXXXXX5038) | 0.0% | 3,462 | `541778XXXXXX4275`, `541778XXXXXX8036`, `541778XXXXXX8051` |
| 10 | **`Authorization Number`** | Approval authorization code from issuer/network | Auth Code (Alphanumeric string) | 0.1% | 28,694 | `7R9C7G`, `X7IYAF`, `GE6WO2` |
| 11 | **`arn`** | Acquirer Reference Number (ARN) for transaction tracing | ARN (Numeric/alphanumeric string) | 0.0% | 48,740 | `05411296272288074501311/2`, `05334906272367200497764/2`, `55419216273207457087502/2` |
| 12 | **`Transaction Currency`** | Currency in which transaction was originated | Txn Currency (ISO 3-letter alpha) | 0.0% | 44 | `USD`, `GBP`, `CNY` |
| 13 | **`Transaction Amount`** | Amount in original transaction currency | Txn Amount (Decimal numeric) | 0.0% | 8,389 | `0.06`, `0.13`, `0.07` |
| 14 | **`Settlement Currency`** | Currency used for clearing / settlement | Settlement Currency (ISO 3-letter alpha) | 0.07% | 12 | `USD`, `GBP`, `AUD` |
| 15 | **`Settlement Amount`** | Amount settled with payment network | Settlement Amount (Decimal numeric) | 0.0% | 7,247 | `0.06`, `0.13`, `0.07` |
| 16 | **`Billing Currency`** | Currency billed to cardholder wallet/account | Billing Currency (ISO 3-letter alpha) | 0.0% | 12 | `USD`, `GBP`, `CAD` |
| 17 | **`Billing Amount`** | Amount billed to cardholder wallet/account (USD for forex) | Billing Amount (Decimal numeric) | 0.0% | 8,079 | `0.06`, `0.13`, `0.07` |
| 18 | **`Conversion Rate`** | Exchange conversion rate applied between currencies | FX Rate (Decimal numeric) | 0.0% | 973 | `0.0`, `1.0`, `0.1489691` |
| 19 | **`Transaction Date`** | Timestamp when transaction was authorized | Txn Timestamp (DD/MM/YYYY HH:MM:SS) | 0.0% | 22,600 | `29/09/2026 20:34:58`, `28/09/2026 00:00:00`, `29/09/2026 00:00:00` |
| 20 | **`Markup Fee`** | Foreign exchange markup fee amount | Markup Fee (Decimal numeric) | 0.0% | 763 | `0.0`, `0.07`, `0.06` |
| 21 | **`Card Acceptor ID`** | Merchant / Card Acceptor identification code | Card Acceptor ID (Alphanumeric string) | 0.2% | 9,652 | `000001050537935`, `198564538      `, `690694302025518` |
| 22 | **`Total Fees Currency`** | Currency denomination of total fees | Fee Currency (ISO 3-letter alpha) | 0.0% | 12 | `USD`, `GBP`, `CAD` |
| 23 | **`Total Fees & Charges`** | Total fees and charges assessed on transaction | Total Fees (Decimal numeric) | 0.0% | 782 | `0.0`, `0.08`, `0.07` |
| 24 | **`Reversal Flag`** | Reversal indicator (Original, Reversal, Partial) | Reversal Flag (Text) | 0.0% | 2 | `Original`, `Reversal` |
| 25 | **`Terminal ID`** | Point of Sale or ATM Terminal identifier | Terminal ID (Alphanumeric string / padded) | 46.56% | 11,631 | `33840610`, `MTQBVESJ`, `77459535` |
| 26 | **`ECOMM Indicator`** | Electronic commerce / 3D Secure indicator | E-Commerce Flag (Text / '-') | 99.01% | 2 | `212`, `210` |
| 27 | **`UCAF Indicator`** | Universal Cardholder Authentication Field status | UCAF Flag (Text / '-') | 100.0% | 0 |  |
| 28 | **`Transaction Fees`** | Base transaction fee amount | Fee Amount (Decimal numeric) | 0.0% | 14 | `0.0`, `1.0`, `1.5` |
| 29 | **`Tax Amount`** | Taxes applied to fees (GST/VAT) | Tax Amount (Decimal numeric) | 0.0% | 14 | `0.0`, `0.9`, `1.26` |
| 30 | **`mcc`** | Merchant Category Code concatenated with business description | MCC & Desc (e.g. 6011-Member Financial...) | 40.08% | 192 | `5814-Fast Food Restaurants`, `4814-Calls Through Use of Magnetic Stripe Reading Telephones`, `4131-Bus Lines` |
| 31 | **`Tolerance Type`** | Tolerance classification for authorizations | Tolerance Type (Text / '-') | 0.0% | 1 | `PLUS(+)` |
| 32 | **`Tolerance Unit`** | Tolerance percentage or fixed unit amount | Tolerance Unit (Decimal numeric) | 0.0% | 1 | `0` |
| 33 | **`CBS Transaction ID`** | Core Banking System transaction reference number | CBS ID (Numeric string / '-') | 100.0% | 0 |  |
| 34 | **`Foreign Currency Transaction`** | Indicator if transaction involves cross-currency | FX Flag (Yes / No / '-') | 100.0% | 0 |  |
| 35 | **`Agent Entity Name`** | Name of agent or partner issuing entity | Agent Name (Text / '-') | 100.0% | 0 |  |
| 36 | **`Branch Entity ID`** | Branch identification code | Branch ID (Alphanumeric string / '-') | 100.0% | 0 |  |
| 37 | **`Branch Entity Name`** | Name of issuing branch | Branch Name (Text / '-') | 100.0% | 0 |  |
| 38 | **`Agency Name`** | Agency or distributor entity name | Agency Name (Text / '-') | 100.0% | 0 |  |
| 39 | **`Wallet Number`** | Unique cardholder customer wallet / account identifier | Wallet ID (Masked string e.g. 201202XXXXXX4022) | 0.0% | 330 | `210415XXXXXX3022`, `210415XXXXXX5022`, `210415XXXXXX9022` |
| 40 | **`Trace Audit Number`** | System Trace Audit Number (STAN) | STAN (Numeric string) | 0.74% | 28,127 | `837674`, `776084`, `698015` |
| 41 | **`Merchant Name & Location`** | Merchant name and geographic location string | Merchant Details (Text) | 0.63% | 9,937 | `GST MARKUP   `, `REV GST MARKUP   `, `DOMINO S PIZZA UK AND MILTON KEYNES  GBR` |
| 42 | **`Settlement Date`** | Date settlement cleared with network | Settlement Date (DD/MM/YYYY or '-') | 40.51% | 87 | `30/09/2026 00:00:00`, `28/09/2026 00:00:00`, `27/09/2026 00:00:00` |
| 43 | **`MultiClearing Indicator`** | Flag indicating multi-clearing / split shipment | MultiClearing (Yes / No / '-') | 94.94% | 4 | `1400-Not authorized due to other reason`, `1452-Duplicate transaction`, `1403- Partial amount, multi-clearing` |
| 44 | **`MultiClearing Total Amount`** | Total amount across split clearings | MultiClearing Amount (Decimal / '-') | 99.99% | 4 | `6.93`, `108.86`, `434.41` |
| 45 | **`MultiClearing Seq No`** | Sequence number of current clearing slice | Clearing Seq (Numeric / '-') | 100.0% | 0 |  |
| 46 | **`MultiClearing Seq Count`** | Total count of clearing slices | Clearing Count (Numeric / '-') | 100.0% | 0 |  |
| 47 | **`DR/CR to Cardholder`** | Debit or Credit impact on cardholder balance | DR / CR Indicator (DR / CR) | 0.0% | 2 | `DR`, `CR` |
| 48 | **`DCC Pre-Conversion Amount`** | Dynamic Currency Conversion original amount | DCC Amount (Decimal / '-') | 100.0% | 1 | `44.50` |
| 49 | **`DCC Pre-Conversion Currency`** | Dynamic Currency Conversion currency code | DCC Currency (ISO alpha / '-') | 100.0% | 1 | `EUR` |
| 50 | **`Corporate Name`** | Corporate customer name if corporate program | Corporate Name (Text / '-') | 100.0% | 0 |  |
| 51 | **`Transaction Originated From`** | Originating interface or system | Origin System (Text / '-') | 41.1% | 59 | `GBR`, `AUT`, `CHN` |
| 52 | **`Device Number Alias`** | Secondary alias for payment device | Device Alias (Text / '-') | 100.0% | 0 |  |
| 53 | **`memo`** | Transaction memo or operator notes | Memo (Text / '-') | 99.9% | 8 | `BT`, `ALERT FEE`, `bt` |
| 54 | **`Virtual Card Number`** | Virtual card identifier if tokenized | Virtual PAN (Masked / '-') | 100.0% | 0 |  |
| 55 | **`Cashback Amount`** | Cashback reward amount credited | Cashback (Decimal numeric) | 100.0% | 0 |  |
| 56 | **`Cashback Currency`** | Currency of cashback reward | Cashback Currency (ISO alpha / '-') | 100.0% | 0 |  |
| 57 | **`Partial Approval`** | Indicator if partial amount authorization occurred | Partial Approval (Yes / No / '-') | 100.0% | 0 |  |
| 58 | **`Card Pack Id`** | Fulfillment card pack identifier | Card Pack ID (Alphanumeric / '-') | 0.0% | 3,794 | `ECDC010000015314`, `ECDC010000016002`, `ECDC010000016003` |
| 59 | **`Corporate Id`** | Corporate client identifier | Corporate ID (Alphanumeric / '-') | 100.0% | 0 |  |
| 60 | **`Travel Type`** | Travel classification flag | Travel Type (Text / '-') | 100.0% | 0 |  |
| 61 | **`Token Transaction Type`** | Tokenization payment classification | Token Type (Text / '-') | 100.0% | 1 | `Token DSRP with UCAF` |
| 62 | **`Loyalty Points Earned`** | Loyalty rewards points accrued | Loyalty Points (Decimal numeric) | 0.0% | 1 | `0` |
| 63 | **`CUSTOM DATA 1`** | Custom host application field 1 | Custom Field 1 (Text / '-') | 100.0% | 0 |  |
| 64 | **`CUSTOM DATA 2`** | Custom host application field 2 | Custom Field 2 (Text / '-') | 100.0% | 0 |  |
| 65 | **`Reference Number`** | Host / network reference number | Reference Number (Alphanumeric string) | 0.47% | 28,653 | `022059`, `627000776084`, `627200698015` |
| 66 | **`State/Province`** | Merchant state or province location | State / Province (Text / '-') | 100.0% | 0 |  |
| 67 | **`Recurring Additional Data`** | Recurring payment metadata | Recurring Data (Text / '-') | 99.99% | 1 | `0000000000000          000` |
| 68 | **`source_file`** | Source batch file name from which record was ingested | Source Filename (Text) | 0.0% | 26 | `30-09-2026_T2L2 MASTERCARD SPEND REPORT.DT.30-09-2026`, `28-09-2026_T2L2 MASTERCARD SPEND REPORT.DT.28-09-2026`, `29-09-2026_T2L2 MASTERCARD SPEND REPORT.DT.29-09-2026` |