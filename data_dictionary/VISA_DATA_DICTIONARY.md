# VISA Data Dictionary

**Source Dataset**: `VISA` feed (154,567 total rows analyzed)
**Analysis Scope**: 100% of rows analyzed across data types, null rates, cardinality, and formats.

| # | Column Name | Business Description | Storage Type & Format | Null Rate | Distinct Values | Sample Non-Null Values |
|---|---|---|---|---|---|---|
| 1 | **`spbusd`** | Business / processing date for the record | Business Date (ISO YYYY-MM-DD) | 0.0% | 29 | `2026-09-28`, `2026-09-29`, `2026-09-30` |
| 2 | **`spbin`** | Bank Identification Number / card product range identifier | Card BIN (Numeric) | 0.0% | 2 | `43673300`, `43673301` |
| 3 | **`spdesc`** | Card program description | Program Name (Text) | 0.0% | 2 | `EbixCash Globetrotter Travel Card`, `ESAF Program` |
| 4 | **`spacct`** | Unique account identifier associated with the cardholder | Account Number (P-prefixed string) | 0.0% | 11,640 | `P000000000000866990`, `P000000000000867044`, `P000000000000867108` |
| 5 | **`spname`** | Cardholder full name | Customer Name (Upper-case text) | 0.0% | 11,409 | `SUNDARAM RAJKUMAR`, `GURUPRASAD TIRUVANAMALAI`, `AGNELLO SEQUEIRA` |
| 6 | **`spctyp`** | Cardholder classification type (e.g. Retail) | Customer Classification (Text) | 0.0% | 2 | `Retail`, `Corporate` |
| 7 | **`spcnam`** | Corporate / company name (blank if retail) | Corporate Name (Text / blank) | 94.88% | 2 | `TATA COMM TRANSFORMATION`, `AIR INDIA LTD` |
| 8 | **`spcard`** | Masked card number for transaction security | Masked PAN (e.g. 436733******1552) | 0.0% | 7,006 | `436733******1552`, `436733******5413`, `436733******2733` |
| 9 | **`spczid`** | Customer / issuer-side citizen/client identifier | Client ID (P-prefixed string) | 0.0% | 11,640 | `P7447628`, `Z4635846`, `Z2678866` |
| 10 | **`spmcat`** | Merchant Category Code (MCC) classifying vendor business | MCC Code (4-digit numeric string) | 0.0% | 369 | `5814`, `5499`, `5812` |
| 11 | **`SPTRN$`** | Original transaction amount in local merchant currency | Transaction Amount (Decimal numeric) | 0.0% | 19,592 | `12.18`, `39.4`, `10.98` |
| 12 | **`sptrcc`** | ISO currency code of the transaction amount | Transaction Currency (ISO 3-letter alpha) | 0.0% | 92 | `GBP`, `USD`, `AUD` |
| 13 | **`spdbcr`** | Debit or Credit transaction indicator | DR / CR Indicator (DB / CR) | 0.0% | 2 | `DB`, `CR` |
| 14 | **`sppucc`** | Posted / purchase currency code | Posted Currency (ISO 3-letter alpha) | 0.0% | 10 | `GBP`, `USD`, `AUD` |
| 15 | **`sputa`** | Transaction amount in posted/purchase currency (signed) | Posted Amount (Signed decimal numeric) | 0.0% | 16,764 | `-12.18`, `-39.4`, `-10.98` |
| 16 | **`spfeam`** | Fee amount charged on transaction | Fee Amount (Decimal numeric) | 0.0% | 67 | `0.0`, `-5.0`, `-0.5` |
| 17 | **`spfgst`** | Goods and Services Tax (GST) applied to fee | Fee GST Amount (Decimal numeric) | 0.0% | 62 | `0.0`, `-0.9`, `-0.09` |
| 18 | **`spmrkp`** | Currency conversion markup fee amount | Markup Amount (Decimal numeric) | 0.0% | 1,848 | `0.0`, `-0.13`, `-12.36` |
| 19 | **`spmgst`** | GST applied to markup fee | Markup GST Amount (Decimal numeric) | 0.0% | 796 | `0.0`, `-0.02`, `-2.22` |
| 20 | **`spptam`** | Total posted transaction amount including fee adjustments | Total Posted Amount (Signed decimal) | 0.0% | 18,211 | `-12.18`, `-39.4`, `-10.98` |
| 21 | **`spmusa`** | Spend Merchant / Settlement USD equivalent amount | USD Equivalent Amount (Decimal numeric) | 0.0% | 18,168 | `16.16`, `52.28`, `14.57` |
| 22 | **`sptdes`** | Short transaction classification description | Transaction Type (e.g. MERCHANT PURCHASE, ATM) | 0.0% | 7 | `MERCHANT PURCHASE`, `ATM CASH WITHDRAWAL`, `BALANCE INQUIRY` |
| 23 | **`spldes`** | Long transaction description with merchant name and country | Merchant Name & Location (Text) | 0.0% | 65,320 | `CHOPSTIX                 BEACONSFIELD GB`, `MARKS & SPENCER SACA     BEACONSFIELD GB`, `GDK Beaconsfield ServicesBeaconsfield GB` |
| 24 | **`spstan`** | System Trace Audit Number (STAN) transaction trace reference | STAN Trace Number (Numeric string) | 0.0% | 154,543 | `1512628449`, `1512637444`, `1512640103` |
| 25 | **`spdate`** | Transaction execution date (DDMMYYYY format) | Transaction Date (DDMMYYYY string) | 0.0% | 30 | `28092026`, `27092026`, `29092026` |
| 26 | **`sptime`** | Transaction execution time (HHMMSS format) | Transaction Time (HHMMSS string) | 0.0% | 22,702 | `162026`, `161231`, `162636` |
| 27 | **`spcaid`** | Card Acceptor ID identifying merchant terminal owner | Card Acceptor ID (Numeric string) | 0.0% | 60,122 | `70132904`, `23725185`, `415021293637018` |
| 28 | **`spcati`** | Card Acceptor Terminal Identifier / category identifier | Terminal ID (8-digit string with leading zeros) | 0.39% | 79,593 | `00000003`, `16455338`, `64080797` |
| 29 | **`source_file`** | Source batch file name from which record was ingested | Source Filename (Text) | 0.0% | 29 | `28-09-2026_SPERP280926003427`, `29-09-2026_SPERP290926002714`, `30-09-2026_SPERP300926004133` |