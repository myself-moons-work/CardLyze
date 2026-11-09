-- ==============================================================================
-- Task 1: TMS-ATM High-Risk Transaction Monitoring Alert Logic (T-SQL / MS SQL Server)
-- ==============================================================================
-- Card Providers: VISA, PineLabs, Vegapay
-- ATM MCCs: 6011 (Automated Cash), 6010 (Manual Cash), 6050 (Quasi-Cash), 6051 (Foreign Currency / Money Orders)
-- Primary Monitoring Date: Cardholder Transaction Date (spdate, Transaction Date, Transaction Date)
-- Alert Rule: Transaction Frequency > 3 AND Total USD Equivalent > $1500 per individual per day.
-- Output: 
--   1. Flagged individuals (+1 Alert with Date, Frequency, Total USD Equivalent)
--   2. Unmodified raw source records for all flagged individuals (or a selected individual).
-- ==============================================================================

-- ==============================================================================
-- 1. VISA SPEND TABLE
-- ==============================================================================
-- Assumed Table: [dbo].[visa_spend]
-- Primary Date: spdate (Format: DDMMYYYY / YYYY-MM-DD)
-- Target Date Parameter (ISO YYYY-MM-DD):
DECLARE @VisaTargetDate DATE = '2026-10-26';
-- Optional Filter: Set to a specific Account Number for an individual report, or NULL for all flagged individuals:
DECLARE @VisaIndividualAccount VARCHAR(50) = NULL; -- e.g. 'P00000000002496445'

-- Query 1A: Flagged Individuals Alert Summary
;WITH VisaAtmFiltered AS (
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

-- Query 1B: Retrieve Full Unmodified Transactions for Flagged Individuals (All or Specific)
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

-- ==============================================================================
-- 2. PINELABS SPEND TABLE
-- ==============================================================================
-- Assumed Table: [dbo].[pinelabs_spend]
-- Primary Date: [Transaction Date] (Format: 'DD/MM/YYYY HH:MM:SS', 'DD/MM/YYYY', or native DATETIME)
DECLARE @PineLabsTargetDate DATE = '2026-09-30';
-- Optional Filter: Set to a specific Wallet Number for an individual report, or NULL for all flagged individuals:
DECLARE @PineLabsIndividualWallet VARCHAR(50) = NULL; -- e.g. '250602XXXXXX9022'

-- Query 2A: Flagged Individuals Alert Summary
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

-- Query 2B: Retrieve Full Unmodified Transactions for Flagged Individuals (All or Specific)
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

-- ==============================================================================
-- 3. VEGAPAY SPEND TABLE
-- ==============================================================================
-- Assumed Table: [dbo].[vegapay_spend]
-- Primary Date: [Transaction Date] (Format: 'DD-MM-YYYY', 'DD/MM/YYYY', or 'YYYY-MM-DD')
DECLARE @VegapayTargetDate DATE = '2026-09-30';
-- Optional Filter: Set to a specific Account Number for an individual report, or NULL for all flagged individuals:
DECLARE @VegapayIndividualAccount VARCHAR(50) = NULL;

-- Query 3A: Flagged Individuals Alert Summary
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

-- Query 3B: Retrieve Full Unmodified Transactions for Flagged Individuals (All or Specific)
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
