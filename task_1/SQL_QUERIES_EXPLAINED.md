# SQL Queries Explained: Step-by-Step & Line-by-Line (Transaction Date Logic)

This document explains the Microsoft SQL Server (T-SQL) queries written in `task_1/tms_atm_task1_queries.sql` in plain, easy-to-understand language.

---

## The Big Picture: What Are We Trying to Do?

Our goal is **Transaction Monitoring (TMS-ATM)**:
1. Every day, look at transactions across 3 card providers: **VISA**, **PineLabs**, and **Vegapay**.
2. Group records by the **actual cardholder transaction date** (`spdate` for VISA, `Transaction Date` for PineLabs, `Transaction Date` for Vegapay).
3. Find anyone withdrawing cash at an ATM (**High-risk MCC codes**: `6011`, `6010`, `6050`, `6051`).
4. Check two alert rules for each person on that specific transaction day:
   - **Rule 1 (Frequency)**: Did they make **more than 3** ATM transactions? (`COUNT > 3`)
   - **Rule 2 (Amount)**: Did their total withdrawals exceed **$1,500 USD**? (`SUM > $1500`)
5. If **BOTH** rules are met:
   - **Output 1 (Summary)**: Give them **+1 Alert** and show their name, account, transaction count, and total USD.
   - **Output 2 (Transactions)**: Pull out their exact, un-modified raw transaction records so a fraud investigator can examine them.

---

## How Data Flows Through the Queries

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAW SOURCE TABLE IN SQL                      │
│                  (e.g. 154,567 rows in VISA)                    │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
   [STEP 1: WHERE Filter (Single Transaction Date + ATM MCCs)]
   Throws away other dates and non-ATM retail spend (groceries, etc.)
                                 │
                                 ▼
             Filtered ATM Rows for the Transaction Day
                                 │
                                 ▼
          [STEP 2: GROUP BY (Account / Wallet Number)]
    Bundles all transactions of each individual together on that day
                                 │
                                 ▼
      [STEP 3: HAVING Filter (Frequency > 3 AND Total > $1500)]
   Keeps ONLY individuals who breached both high-risk thresholds
                                 │
                                 ▼
                     FINAL FLAGGED INDIVIDUALS
                      (e.g. 2 alerts for VISA)
```

---

## 1. VISA SPEND TABLE (`[dbo].[visa_spend]`)

### Query 1A: Flagged Individuals Alert Summary

```sql
DECLARE @VisaTargetDate DATE = '2026-10-26';
DECLARE @VisaIndividualAccount VARCHAR(50) = NULL;
```
* **What it does**: Sets up the target transaction date we want to check (e.g. October 26, 2026).
* **Why use `DATE` type?**: Setting the variable type as `DATE` ensures SQL Server compares dates natively, which allows SQL Server to use indexes efficiently rather than doing slow string scans.

```sql
;WITH VisaAtmFiltered AS (
```
* **What it does**: Opens a **CTE (Common Table Expression)**. Think of a CTE as a temporary named result box that exists only while this query runs.
* **Why the leading semicolon `;`?**: In T-SQL, Microsoft SQL Server requires that whatever statement comes before `WITH` ends with a semicolon. Starting with `;WITH` guarantees the query never crashes with syntax error `4672`.

```sql
    SELECT 
        spacct,
        spname,
        COALESCE(
            TRY_CONVERT(DATE, 
                LEFT(RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8), 2) + '/' +
                SUBSTRING(RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8), 3, 2) + '/' +
                RIGHT(RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8), 4), 
                103
            ),
            TRY_CONVERT(DATE, spdate, 120),
            TRY_CONVERT(DATE, spdate)
        ) AS tx_date_normalized,
        ABS(TRY_CAST(REPLACE(CAST(spmusa AS VARCHAR(50)), ',', '') AS DECIMAL(18, 2))) AS usd_amount
    FROM [dbo].[visa_spend]
```
* **What happens to actual data**:
  * `spacct`: The unique customer account number (e.g., `'P00000000002496445'`).
  * `spname`: The customer name (e.g., `'BHARGAVI SUDUGULA'`).
  * `spdate`: The actual transaction date. In raw VISA data, this is stored as an 8-digit or 7-digit string (e.g. `'26102026'` or `'1102026'` where leading zero was dropped for the 1st of October).
* **How `spdate` parsing works**:
  1. `RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8)` ensures every date is padded to exactly 8 characters (e.g. `'1102026'` becomes `'01102026'`).
  2. Slices into `DD/MM/YYYY`: Day (`LEFT(d, 2)`), Month (`SUBSTRING(d, 3, 2)`), Year (`RIGHT(d, 4)`).
  3. `TRY_CONVERT(DATE, ..., 103)`: Parses British format `DD/MM/YYYY` into a native SQL `DATE`.
  4. `COALESCE`: If `spdate` was already imported as an ISO string (`YYYY-MM-DD`) or native `DATE`, it handles that too.
* **Why `ABS(...)` and `REPLACE` on `spmusa`?**:
  * `spmusa`: The USD amount.
  * In banking, an ATM cash withdrawal is money leaving the account (a debit), so some systems record it as `-500.00`. `ABS` ensures all cash debits are treated as positive sums.
  * `REPLACE(..., ',', '')` strips accidental thousands separators before decimal casting.

```sql
    WHERE COALESCE(
            TRY_CONVERT(DATE, 
                LEFT(RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8), 2) + '/' +
                SUBSTRING(RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8), 3, 2) + '/' +
                RIGHT(RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8), 4), 
                103
            ),
            TRY_CONVERT(DATE, spdate, 120),
            TRY_CONVERT(DATE, spdate)
          ) = @VisaTargetDate
      AND LTRIM(RTRIM(spmcat)) IN ('6011', '6010', '6050', '6051')
),
```
* Filters only records where the actual swipe/ATM withdrawal happened on the target date, and where the category is an ATM cash withdrawal MCC.

```sql
VisaFlaggedIndividuals AS (
    SELECT 
        spacct AS account_number,
        MAX(spname) AS individual_name,
        tx_date_normalized AS alert_date,
        COUNT(*) AS transaction_frequency,
        SUM(usd_amount) AS total_usd_equivalent,
        1 AS alert_count
    FROM VisaAtmFiltered
    GROUP BY spacct, tx_date_normalized
    HAVING COUNT(*) > 3 
       AND SUM(usd_amount) > 1500.00
)
SELECT * FROM VisaFlaggedIndividuals
ORDER BY total_usd_equivalent DESC;
```
* Groups by account and transaction date. Evaluates if the person made **> 3 withdrawals** AND withdrew **> $1,500.00 USD**.

---

### Query 1B: Retrieve Full Unmodified Transactions for Flagged Individuals

```sql
;WITH VisaFlaggedList AS (
    SELECT spacct
    FROM [dbo].[visa_spend]
    WHERE COALESCE(
            TRY_CONVERT(DATE, 
                LEFT(RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8), 2) + '/' +
                SUBSTRING(RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8), 3, 2) + '/' +
                RIGHT(RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8), 4), 
                103
            ),
            TRY_CONVERT(DATE, spdate, 120),
            TRY_CONVERT(DATE, spdate)
          ) = @VisaTargetDate
      AND LTRIM(RTRIM(spmcat)) IN ('6011', '6010', '6050', '6051')
    GROUP BY spacct
    HAVING COUNT(*) > 3 
       AND SUM(ABS(TRY_CAST(REPLACE(CAST(spmusa AS VARCHAR(50)), ',', '') AS DECIMAL(18, 2)))) > 1500.00
)
SELECT v.*
FROM [dbo].[visa_spend] v
INNER JOIN VisaFlaggedList f ON v.spacct = f.spacct
WHERE COALESCE(
        TRY_CONVERT(DATE, 
            LEFT(RIGHT('00000000' + LTRIM(RTRIM(CAST(v.spdate AS VARCHAR(8)))), 8), 2) + '/' +
            SUBSTRING(RIGHT('00000000' + LTRIM(RTRIM(CAST(v.spdate AS VARCHAR(8)))), 8), 3, 2) + '/' +
            RIGHT(RIGHT('00000000' + LTRIM(RTRIM(CAST(v.spdate AS VARCHAR(8)))), 8), 4), 
            103
        ),
        TRY_CONVERT(DATE, v.spdate, 120),
        TRY_CONVERT(DATE, v.spdate)
      ) = @VisaTargetDate
  AND LTRIM(RTRIM(v.spmcat)) IN ('6011', '6010', '6050', '6051')
  AND (@VisaIndividualAccount IS NULL OR v.spacct = @VisaIndividualAccount)
ORDER BY v.spacct, v.sptime;
GO
```
* **What it does**:
  1. Finds the flagged accounts using `spdate`.
  2. Joins back to raw table `v` to extract all 29 original columns without any modifications.
  3. Filter parameter `@VisaIndividualAccount`: Set to `NULL` to pull all flagged individuals, or provide an account number to generate a single individual's report.
  4. Orders by account, then chronological time (`sptime`).

---

## 2. PINELABS SPEND TABLE (`[dbo].[pinelabs_spend]`)

### Query 2A: Flagged Individuals Alert Summary

```sql
DECLARE @PineLabsTargetDate DATE = '2026-09-30';
DECLARE @PineLabsIndividualWallet VARCHAR(50) = NULL;

;WITH PineAtmFiltered AS (
    SELECT 
        [Wallet Number] AS wallet_number,
        [Device Number] AS device_number,
        COALESCE(
            TRY_CONVERT(DATE, LEFT([Transaction Date], 10), 103),
            TRY_CONVERT(DATE, [Transaction Date], 120),
            TRY_CONVERT(DATE, [Transaction Date])
        ) AS tx_date_normalized,
        ABS(TRY_CAST(REPLACE([Billing Amount], ',', '') AS DECIMAL(18, 2))) AS usd_amount
    FROM [dbo].[pinelabs_spend]
    WHERE COALESCE(
            TRY_CONVERT(DATE, LEFT([Transaction Date], 10), 103),
            TRY_CONVERT(DATE, [Transaction Date], 120),
            TRY_CONVERT(DATE, [Transaction Date])
          ) = @PineLabsTargetDate
      AND LEFT(LTRIM(RTRIM([mcc])), 4) IN ('6011', '6010', '6050', '6051')
),
PineFlaggedIndividuals AS (
    SELECT 
        wallet_number AS account_number,
        MAX(device_number) AS sample_masked_pan,
        tx_date_normalized AS alert_date,
        COUNT(*) AS transaction_frequency,
        SUM(usd_amount) AS total_usd_equivalent,
        1 AS alert_count
    FROM PineAtmFiltered
    GROUP BY wallet_number, tx_date_normalized
    HAVING COUNT(*) > 3 
       AND SUM(usd_amount) > 1500.00
)
SELECT * FROM PineFlaggedIndividuals
ORDER BY total_usd_equivalent DESC;
```
* **`[Transaction Date]`**: In raw PineLabs data, this column contains timestamp strings like `'29/09/2026 20:34:58'`.
* **`LEFT([Transaction Date], 10)`**: Extracts the first 10 characters (`'29/09/2026'`).
* **`TRY_CONVERT(DATE, ..., 103)`**: Converts British format `DD/MM/YYYY` into SQL `DATE`.
* **`COALESCE(...)`**: Safely handles ISO strings (`YYYY-MM-DD`) or native `DATETIME` columns without crashing.
* **`LEFT(LTRIM(RTRIM([mcc])), 4)`**: Slices the 4-digit code out of long descriptions like `'6011-Member Financial Institution...'`.

---

### Query 2B: Retrieve Full Unmodified Transactions for PineLabs

```sql
;WITH PineFlaggedList AS (
    SELECT [Wallet Number] AS wallet_number
    FROM [dbo].[pinelabs_spend]
    WHERE COALESCE(
            TRY_CONVERT(DATE, LEFT([Transaction Date], 10), 103),
            TRY_CONVERT(DATE, [Transaction Date], 120),
            TRY_CONVERT(DATE, [Transaction Date])
          ) = @PineLabsTargetDate
      AND LEFT(LTRIM(RTRIM([mcc])), 4) IN ('6011', '6010', '6050', '6051')
    GROUP BY [Wallet Number]
    HAVING COUNT(*) > 3 
       AND SUM(ABS(TRY_CAST(REPLACE([Billing Amount], ',', '') AS DECIMAL(18, 2)))) > 1500.00
)
SELECT p.*
FROM [dbo].[pinelabs_spend] p
INNER JOIN PineFlaggedList f ON p.[Wallet Number] = f.wallet_number
WHERE COALESCE(
        TRY_CONVERT(DATE, LEFT(p.[Transaction Date], 10), 103),
        TRY_CONVERT(DATE, p.[Transaction Date], 120),
        TRY_CONVERT(DATE, p.[Transaction Date])
      ) = @PineLabsTargetDate
  AND LEFT(LTRIM(RTRIM(p.[mcc])), 4) IN ('6011', '6010', '6050', '6051')
  AND (@PineLabsIndividualWallet IS NULL OR p.[Wallet Number] = @PineLabsIndividualWallet)
ORDER BY p.[Wallet Number], p.[Transaction Date];
GO
```
* Extracts all 68 raw columns for flagged PineLabs wallets based on `[Transaction Date]`.

---

## 3. VEGAPAY SPEND TABLE (`[dbo].[vegapay_spend]`)

### Query 3A: Flagged Individuals Alert Summary

```sql
DECLARE @VegapayTargetDate DATE = '2026-09-30';
DECLARE @VegapayIndividualAccount VARCHAR(50) = NULL;

;WITH VegapayAtmFiltered AS (
    SELECT 
        [Account Number] AS account_number,
        [Customer ID] AS customer_id,
        [Card Holder Name] AS cardholder_name,
        COALESCE(
            TRY_CONVERT(DATE, [Transaction Date], 105),           -- DD-MM-YYYY
            TRY_CONVERT(DATE, LEFT([Transaction Date], 10), 103),  -- DD/MM/YYYY
            TRY_CONVERT(DATE, [Transaction Date], 120),           -- YYYY-MM-DD
            TRY_CONVERT(DATE, [Transaction Date])
        ) AS tx_date_normalized,
        ABS(TRY_CAST(REPLACE([Billing Amount], ',', '') AS DECIMAL(18, 2))) AS usd_amount
    FROM [dbo].[vegapay_spend]
    WHERE COALESCE(
            TRY_CONVERT(DATE, [Transaction Date], 105),
            TRY_CONVERT(DATE, LEFT([Transaction Date], 10), 103),
            TRY_CONVERT(DATE, [Transaction Date], 120),
            TRY_CONVERT(DATE, [Transaction Date])
          ) = @VegapayTargetDate
      AND LTRIM(RTRIM(CAST([MCC] AS VARCHAR(10)))) IN ('6011', '6010', '6050', '6051')
),
VegapayFlaggedIndividuals AS (
    SELECT 
        account_number,
        MAX(customer_id) AS customer_id,
        MAX(cardholder_name) AS individual_name,
        tx_date_normalized AS alert_date,
        COUNT(*) AS transaction_frequency,
        SUM(usd_amount) AS total_usd_equivalent,
        1 AS alert_count
    FROM VegapayAtmFiltered
    GROUP BY account_number, tx_date_normalized
    HAVING COUNT(*) > 3 
       AND SUM(usd_amount) > 1500.00
)
SELECT * FROM VegapayFlaggedIndividuals
ORDER BY total_usd_equivalent DESC;
```
* **`[Transaction Date]`**: In Vegapay, transaction dates are stored as `'30-09-2026'` (`DD-MM-YYYY`).
* **`TRY_CONVERT(DATE, ..., 105)`**: Style 105 in SQL Server is `DD-MM-YYYY`. It correctly identifies 30 as Day and 09 as Month.
* If a cell has a placeholder like `'-'`, `TRY_CONVERT` safely returns `NULL` without breaking the query.

---

### Query 3B: Retrieve Full Unmodified Transactions for Vegapay

```sql
;WITH VegapayFlaggedList AS (
    SELECT [Account Number] AS account_number
    FROM [dbo].[vegapay_spend]
    WHERE COALESCE(
            TRY_CONVERT(DATE, [Transaction Date], 105),
            TRY_CONVERT(DATE, LEFT([Transaction Date], 10), 103),
            TRY_CONVERT(DATE, [Transaction Date], 120),
            TRY_CONVERT(DATE, [Transaction Date])
          ) = @VegapayTargetDate
      AND LTRIM(RTRIM(CAST([MCC] AS VARCHAR(10)))) IN ('6011', '6010', '6050', '6051')
    GROUP BY [Account Number]
    HAVING COUNT(*) > 3 
       AND SUM(ABS(TRY_CAST(REPLACE([Billing Amount], ',', '') AS DECIMAL(18, 2)))) > 1500.00
)
SELECT vg.*
FROM [dbo].[vegapay_spend] vg
INNER JOIN VegapayFlaggedList f ON vg.[Account Number] = f.account_number
WHERE COALESCE(
        TRY_CONVERT(DATE, vg.[Transaction Date], 105),
        TRY_CONVERT(DATE, LEFT(vg.[Transaction Date], 10), 103),
        TRY_CONVERT(DATE, vg.[Transaction Date], 120),
        TRY_CONVERT(DATE, vg.[Transaction Date])
      ) = @VegapayTargetDate
  AND LTRIM(RTRIM(CAST(vg.[MCC] AS VARCHAR(10)))) IN ('6011', '6010', '6050', '6051')
  AND (@VegapayIndividualAccount IS NULL OR vg.[Account Number] = @VegapayIndividualAccount)
ORDER BY vg.[Account Number], vg.[Transaction Date];
GO
```
* Pulls all 61 raw columns for flagged Vegapay accounts based on `[Transaction Date]`.

---

## Quick Reference: Why Each Function Is Used

| SQL Function | Purpose in Plain Words | Example from Actual Data |
| :--- | :--- | :--- |
| `;WITH ... AS` | Creates a temporary table (CTE) for step-by-step filtering without saving clutter to the database. | `VisaAtmFiltered`, `VisaFlaggedIndividuals` |
| `RIGHT('00000000' + col, 8)` | Pads short dates (7 digits) with a leading zero to form a proper 8-digit date (`DDMMYYYY`). | `'1102026'` &rarr; `'01102026'` |
| `TRY_CONVERT(DATE, col, 103)` | Parses British date strings (`DD/MM/YYYY`) into standard SQL date. | `'28/09/2026'` &rarr; `2026-09-28` |
| `TRY_CONVERT(DATE, col, 105)` | Parses hyphenated date strings (`DD-MM-YYYY`) into standard SQL date. | `'30-09-2026'` &rarr; `2026-09-30` |
| `COALESCE(A, B, C)` | Tries format A, then B, then C. Picks the first one that does not fail (`NOT NULL`). | Handles `DDMMYYYY`, `DD/MM/YYYY`, `DD-MM-YYYY`, and native `DATE`. |
| `TRY_CAST(col AS DECIMAL)` | Converts text to numbers safely. Returns `NULL` instead of crashing if a cell contains corrupt text. | `'1998.39'` &rarr; `1998.39` |
| `ABS(number)` | Makes negative numbers positive so debit withdrawals (`-500.00`) add up instead of subtracting. | `-500.00` &rarr; `+500.00` |
| `REPLACE(col, ',', '')` | Removes thousands separators from numbers stored as text. | `'1,500.00'` &rarr; `'1500.00'` |
| `LEFT(col, 4)` | Extracts the first 4 characters from the left. Used to pull MCC code from descriptive text. | `'6011-Member...'` &rarr; `'6011'` |
| `LTRIM(RTRIM(col))` | Strips accidental spaces from both the left and right sides. | `' 6011 '` &rarr; `'6011'` |
| `MAX(name)` | Satisfies SQL's `GROUP BY` requirement to display the cardholder's name without grouping by it. | `'BHARGAVI SUDUGULA'` |
| `HAVING ...` | Filters the summary groups **after** aggregating (`COUNT > 3 AND SUM > 1500`). | Flags accounts exceeding limits. |
| `INNER JOIN` | Links the flagged account list back to the raw table to extract 100% unmodified transaction rows. | Extracts all 29 VISA, 68 PineLabs, or 61 Vegapay columns. |
