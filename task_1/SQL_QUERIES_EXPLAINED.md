# SQL Queries Explained: Step-by-Step & Line-by-Line

This document explains the Microsoft SQL Server (T-SQL) queries written in `task_1/tms_atm_task1_queries.sql` in plain, easy-to-understand language.

---

## The Big Picture: What Are We Trying to Do?

Our goal is **Transaction Monitoring (TMS-ATM)**:
1. Every day, look at transactions across 3 card providers: **VISA**, **PineLabs**, and **Vegapay**.
2. Find anyone withdrawing cash at an ATM (**High-risk MCC codes**: `6011`, `6010`, `6050`, `6051`).
3. Check two alert rules for each person on that specific day:
   - **Rule 1 (Frequency)**: Did they make **more than 3** ATM transactions? (`COUNT > 3`)
   - **Rule 2 (Amount)**: Did their total withdrawals exceed **$1,500 USD**? (`SUM > $1500`)
4. If **BOTH** rules are met:
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
         [STEP 1: WHERE Filter (Single Day + ATM MCCs)]
   Throws away other dates and non-ATM retail spend (groceries, etc.)
                                 │
                                 ▼
                   Filtered ATM Rows for the Day
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
* **What it does**: Sets up the target date we want to check (e.g. October 26, 2026).
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
        spbusd,
        ABS(TRY_CAST(spmusa AS DECIMAL(18, 2))) AS usd_amount
    FROM [dbo].[visa_spend]
```
* **What happens to actual data**:
  * `spacct`: The unique customer account number (e.g., `'P00000000002496445'`).
  * `spname`: The customer name (e.g., `'BHARGAVI SUDUGULA'`).
  * `spbusd`: The settlement/business date (e.g., `'2026-10-26'`).
  * `spmusa`: The USD amount of the transaction.
* **Why `TRY_CAST` instead of `CAST`?**:
  * In real data, sometimes a cell has corrupt text, a blank string `''`, or a symbol. Normal `CAST('abc' AS DECIMAL)` crashes the entire query with an error.
  * `TRY_CAST` is safe: if a cell has valid numbers like `'500.00'`, it converts it; if it encounters corrupted data, it returns `NULL` without stopping the query.
* **Why `ABS(...)`?**:
  * `ABS` stands for **Absolute Value** (making negative numbers positive).
  * In banking, an ATM cash withdrawal is money leaving the account (a debit), so some systems record it as `-500.00`. If you sum `-500.00` and `-600.00`, normal math gives `-1100.00`, which is less than `$1500`! `ABS(-500.00)` turns it into `+500.00` so withdrawals accumulate correctly.

```sql
    WHERE CAST(spbusd AS DATE) = @VisaTargetDate
      AND LTRIM(RTRIM(spmcat)) IN ('6011', '6010', '6050', '6051')
),
```
* **What happens to actual data**:
  * `CAST(spbusd AS DATE) = @VisaTargetDate`: Throws away all records from other dates, keeping only transactions on October 26, 2026.
  * `LTRIM(RTRIM(spmcat))`: Strips accidental leading or trailing spaces (e.g. `' 6011 '` becomes `'6011'`).
  * `IN ('6011', '6010', '6050', '6051')`: Filters only ATM / cash withdrawal categories:
    * `6011`: Automated Cash Disbursements (standard ATM withdrawal).
    * `6010`: Manual Cash Disbursements (bank teller cash).
    * `6050`: Quasi-Cash (cryptocurrency, casino chips).
    * `6051`: Foreign Currency / Money Orders.
  * All shopping, restaurant, and hotel rows are discarded here.

```sql
VisaFlaggedIndividuals AS (
    SELECT 
        spacct AS account_number,
        MAX(spname) AS individual_name,
        spbusd AS alert_date,
        COUNT(*) AS transaction_frequency,
        SUM(usd_amount) AS total_usd_equivalent,
        1 AS alert_count
    FROM VisaAtmFiltered
    GROUP BY spacct, spbusd
    HAVING COUNT(*) > 3 
       AND SUM(usd_amount) > 1500.00
)
```
* **What it does**: Groups the filtered ATM rows by customer account and date.
* **Why `MAX(spname)`?**:
  * In SQL, when you do `GROUP BY spacct, spbusd`, any column you want to show in the `SELECT` list that isn't in the `GROUP BY` must use an aggregate function (`SUM`, `COUNT`, `MAX`, etc.).
  * Since an account number always belongs to the same person, `MAX(spname)` simply picks their name (`'BHARGAVI SUDUGULA'`).
* **Why `HAVING` instead of `WHERE`?**:
  * `WHERE` filters individual rows **before** grouping.
  * `HAVING` filters the groups **after** aggregating. Here, we can only check if `COUNT(*) > 3` and `SUM > 1500` after the customer's transactions have been grouped and added up!
* **Actual Data Example**:
  * Bhargavi Sudugula had 5 ATM withdrawals on `2026-10-26` totaling `$1,998.39`.
  * `COUNT(*) = 5` (which is > 3: **Passes**).
  * `SUM = 1998.39` (which is > 1500: **Passes**).
  * Result: Flagged with `alert_count = 1`!

```sql
SELECT * FROM VisaFlaggedIndividuals
ORDER BY total_usd_equivalent DESC;
```
* **What it does**: Outputs the alert summary list, putting the highest total USD amounts at the top.

---

### Query 1B: Retrieve Full Unmodified Transactions for Flagged Individuals

```sql
;WITH VisaFlaggedList AS (
    SELECT spacct
    FROM [dbo].[visa_spend]
    WHERE CAST(spbusd AS DATE) = @VisaTargetDate
      AND LTRIM(RTRIM(spmcat)) IN ('6011', '6010', '6050', '6051')
    GROUP BY spacct
    HAVING COUNT(*) > 3 
       AND SUM(ABS(TRY_CAST(spmusa AS DECIMAL(18, 2)))) > 1500.00
)
SELECT v.*
FROM [dbo].[visa_spend] v
INNER JOIN VisaFlaggedList f ON v.spacct = f.spacct
WHERE CAST(v.spbusd AS DATE) = @VisaTargetDate
  AND LTRIM(RTRIM(v.spmcat)) IN ('6011', '6010', '6050', '6051')
  AND (@VisaIndividualAccount IS NULL OR v.spacct = @VisaIndividualAccount)
ORDER BY v.spacct, v.sptime;
GO
```
* **What it does**:
  1. `VisaFlaggedList`: First finds the list of account numbers that violated the rule.
  2. `INNER JOIN VisaFlaggedList f ON v.spacct = f.spacct`: Joins back to the original `[dbo].[visa_spend]` table `v`. This pulls every original column (`spbusd`, `spbin`, `spdesc`, `spacct`, `spname`, `sptime`, etc.) with **zero column modifications**.
  3. `(@VisaIndividualAccount IS NULL OR v.spacct = @VisaIndividualAccount)`:
     * If `@VisaIndividualAccount` is `NULL`, it outputs all transactions for all flagged individuals.
     * If an investigator inputs `'P00000000002496445'`, it outputs only that specific individual's report.
  4. `ORDER BY v.spacct, v.sptime`: Orders transactions by account, then chronologically by transaction time (`sptime`).
  5. `GO`: Microsoft SQL Server batch separator. It allows the VISA query block to complete independently.

---

## 2. PINELABS SPEND TABLE (`[dbo].[pinelabs_spend]`)

### Query 2A: Flagged Individuals Alert Summary

```sql
DECLARE @PineLabsTargetDate DATE = '2026-09-30';
DECLARE @PineLabsIndividualWallet VARCHAR(50) = NULL;
```

```sql
;WITH PineAtmFiltered AS (
    SELECT 
        [Wallet Number] AS wallet_number,
        [Device Number] AS device_number,
        COALESCE(
            TRY_CONVERT(DATE, LEFT([Value Date], 10), 103),
            TRY_CONVERT(DATE, [Value Date], 120),
            TRY_CONVERT(DATE, [Value Date])
        ) AS value_date_normalized,
        ABS(TRY_CAST(REPLACE([Billing Amount], ',', '') AS DECIMAL(18, 2))) AS usd_amount
    FROM [dbo].[pinelabs_spend]
```
* **Why square brackets `[Wallet Number]`?**:
  In PineLabs, column names have spaces. In SQL Server, square brackets `[...]` tell SQL that `"Wallet Number"` is a single column name, not two separate keywords.
* **Why the date parsing with `COALESCE` and `TRY_CONVERT`?**:
  * In the real PineLabs file, `[Value Date]` looks like `'30/09/2026 00:00:00'`.
  * `LEFT([Value Date], 10)` takes the first 10 characters: `'30/09/2026'`.
  * `TRY_CONVERT(DATE, ..., 103)`: In SQL Server, **103** is the standard British/European date format (`DD/MM/YYYY`). It correctly understands that `30` is the Day and `09` is September.
  * **What if the database table stores the date in ISO format (`2026-09-30`)?**:
    Style 103 would fail because month 26 doesn't exist. That is why `COALESCE(...)` is used!
    * `COALESCE(A, B, C)` returns the first one that is **NOT NULL**.
    * If British format (103) works -> Uses it.
    * If ISO format (120: `YYYY-MM-DD`) works -> Uses it.
    * If the column is already a native `DATE` or `DATETIME` type -> Uses it.
  * This guarantees the query never breaks regardless of how the IT team imported the table.
* **Why `REPLACE([Billing Amount], ',', '')`?**:
  * In PineLabs, billing amounts can be formatted as text with thousands commas (e.g. `'2,500.00'`).
  * SQL Server cannot convert `'2,500.00'` directly to a decimal if a comma is present.
  * `REPLACE(..., ',', '')` removes the comma (`'2500.00'`), allowing `TRY_CAST` to succeed smoothly.

```sql
    WHERE COALESCE(
            TRY_CONVERT(DATE, LEFT([Value Date], 10), 103),
            TRY_CONVERT(DATE, [Value Date], 120),
            TRY_CONVERT(DATE, [Value Date])
          ) = @PineLabsTargetDate
      AND LEFT(LTRIM(RTRIM([mcc])), 4) IN ('6011', '6010', '6050', '6051')
),
```
* **Why `LEFT(LTRIM(RTRIM([mcc])), 4)`?**:
  * In PineLabs, the MCC column does not just store a 4-digit number; it often stores a full text description, such as:
    `'6011-Member Financial Institution - Automated Cash Disbursements'`
  * `LEFT(..., 4)` slices the first 4 characters: `'6011'`.
  * This matches our ATM list (`'6011', '6010', '6050', '6051'`) perfectly.

```sql
PineFlaggedIndividuals AS (
    SELECT 
        wallet_number AS account_number,
        MAX(device_number) AS sample_masked_pan,
        value_date_normalized AS alert_date,
        COUNT(*) AS transaction_frequency,
        SUM(usd_amount) AS total_usd_equivalent,
        1 AS alert_count
    FROM PineAtmFiltered
    GROUP BY wallet_number, value_date_normalized
    HAVING COUNT(*) > 3 
       AND SUM(usd_amount) > 1500.00
)
SELECT * FROM PineFlaggedIndividuals
ORDER BY total_usd_equivalent DESC;
```
* **Actual Data Example**:
  * Wallet `250602XXXXXX5022` made multiple ATM withdrawals on `2026-09-30` totaling `$6,365.50`.
  * Frequency > 3 AND Total > $1,500: Flagged as Alert #1 with Sample Masked Card `541778XXXXXX7984`.

---

### Query 2B: Retrieve Full Unmodified Transactions for PineLabs

```sql
;WITH PineFlaggedList AS (
    SELECT [Wallet Number] AS wallet_number
    FROM [dbo].[pinelabs_spend]
    WHERE COALESCE(
            TRY_CONVERT(DATE, LEFT([Value Date], 10), 103),
            TRY_CONVERT(DATE, [Value Date], 120),
            TRY_CONVERT(DATE, [Value Date])
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
        TRY_CONVERT(DATE, LEFT(p.[Value Date], 10), 103),
        TRY_CONVERT(DATE, p.[Value Date], 120),
        TRY_CONVERT(DATE, p.[Value Date])
      ) = @PineLabsTargetDate
  AND LEFT(LTRIM(RTRIM(p.[mcc])), 4) IN ('6011', '6010', '6050', '6051')
  AND (@PineLabsIndividualWallet IS NULL OR p.[Wallet Number] = @PineLabsIndividualWallet)
ORDER BY p.[Wallet Number], p.[Transaction Date];
GO
```
* Pulls all 68 raw columns for flagged PineLabs wallets on that date, sorted by Wallet Number and Transaction Date.

---

## 3. VEGAPAY SPEND TABLE (`[dbo].[vegapay_spend]`)

### Query 3A: Flagged Individuals Alert Summary

```sql
DECLARE @VegapayTargetDate DATE = '2026-10-12';
DECLARE @VegapayIndividualAccount VARCHAR(50) = NULL;

;WITH VegapayAtmFiltered AS (
    SELECT 
        [Account Number] AS account_number,
        [Customer ID] AS customer_id,
        [Card Holder Name] AS cardholder_name,
        [Business Date] AS business_date,
        ABS(TRY_CAST(REPLACE([Billing Amount], ',', '') AS DECIMAL(18, 2))) AS usd_amount
    FROM [dbo].[vegapay_spend]
    WHERE CAST([Business Date] AS DATE) = @VegapayTargetDate
      AND LTRIM(RTRIM(CAST([MCC] AS VARCHAR(10)))) IN ('6011', '6010', '6050', '6051')
),
VegapayFlaggedIndividuals AS (
    SELECT 
        account_number,
        MAX(customer_id) AS customer_id,
        MAX(cardholder_name) AS individual_name,
        business_date AS alert_date,
        COUNT(*) AS transaction_frequency,
        SUM(usd_amount) AS total_usd_equivalent,
        1 AS alert_count
    FROM VegapayAtmFiltered
    GROUP BY account_number, business_date
    HAVING COUNT(*) > 3 
       AND SUM(usd_amount) > 1500.00
)
SELECT * FROM VegapayFlaggedIndividuals
ORDER BY total_usd_equivalent DESC;
```
* **What happens to actual data**:
  * `[Business Date]`: In Vegapay, dates are stored in standard ISO format `'2026-10-12'`, so `CAST([Business Date] AS DATE)` matches directly.
  * `CAST([MCC] AS VARCHAR(10))`: Vegapay's MCC column is sometimes stored as an integer (`6011`). Casting to `VARCHAR(10)` ensures clean comparison against `'6011'`, `'6010'`, `'6050'`, `'6051'`.
  * `account_number`: Uses Vegapay's `[Account Number]`.
  * `MAX(customer_id)` and `MAX(cardholder_name)`: Carries the Customer ID and Name alongside the alert.

---

### Query 3B: Retrieve Full Unmodified Transactions for Vegapay

```sql
;WITH VegapayFlaggedList AS (
    SELECT [Account Number] AS account_number
    FROM [dbo].[vegapay_spend]
    WHERE CAST([Business Date] AS DATE) = @VegapayTargetDate
      AND LTRIM(RTRIM(CAST([MCC] AS VARCHAR(10)))) IN ('6011', '6010', '6050', '6051')
    GROUP BY [Account Number]
    HAVING COUNT(*) > 3 
       AND SUM(ABS(TRY_CAST(REPLACE([Billing Amount], ',', '') AS DECIMAL(18, 2)))) > 1500.00
)
SELECT vg.*
FROM [dbo].[vegapay_spend] vg
INNER JOIN VegapayFlaggedList f ON vg.[Account Number] = f.account_number
WHERE CAST(vg.[Business Date] AS DATE) = @VegapayTargetDate
  AND LTRIM(RTRIM(CAST(vg.[MCC] AS VARCHAR(10)))) IN ('6011', '6010', '6050', '6051')
  AND (@VegapayIndividualAccount IS NULL OR vg.[Account Number] = @VegapayIndividualAccount)
ORDER BY vg.[Account Number], vg.[Transaction Date];
GO
```
* Pulls all 61 raw columns for flagged Vegapay accounts, preserving every single source detail.

---

## Quick Reference: Why Each Function Is Used

| SQL Function | Purpose in Plain Words | Example from Actual Data |
| :--- | :--- | :--- |
| `;WITH ... AS` | Creates a temporary table (CTE) for step-by-step filtering without saving clutter to the database. | `VisaAtmFiltered`, `VisaFlaggedIndividuals` |
| `TRY_CAST(col AS DECIMAL)` | Converts text to numbers safely. Returns `NULL` instead of crashing if a cell contains corrupt text. | `'1998.39'` &rarr; `1998.39` |
| `ABS(number)` | Makes negative numbers positive so debit withdrawals (`-500.00`) add up instead of subtracting. | `-500.00` &rarr; `+500.00` |
| `REPLACE(col, ',', '')` | Removes thousands separators from numbers stored as text. | `'1,500.00'` &rarr; `'1500.00'` |
| `TRY_CONVERT(DATE, col, 103)` | Parses British date strings (`DD/MM/YYYY`) into standard SQL date. | `'30/09/2026'` &rarr; `2026-09-30` |
| `LEFT(col, 4)` | Extracts the first 4 characters from the left. Used to pull MCC code from descriptive text. | `'6011-Member...'` &rarr; `'6011'` |
| `LTRIM(RTRIM(col))` | Strips accidental spaces from both the left and right sides. | `' 6011 '` &rarr; `'6011'` |
| `COALESCE(A, B, C)` | Tries format A, then B, then C. Picks the first one that does not fail (`NOT NULL`). | Handles `DD/MM/YYYY`, `YYYY-MM-DD`, and native `DATE`. |
| `MAX(name)` | Satisfies SQL's `GROUP BY` requirement to display the cardholder's name without grouping by it. | `'BHARGAVI SUDUGULA'` |
| `HAVING ...` | Filters the summary groups **after** aggregating (`COUNT > 3 AND SUM > 1500`). | Flags accounts exceeding limits. |
| `INNER JOIN` | Links the flagged account list back to the raw table to extract 100% unmodified transaction rows. | Extracts all 29 VISA, 68 PineLabs, or 61 Vegapay columns. |
