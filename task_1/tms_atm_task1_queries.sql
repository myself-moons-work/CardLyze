-- ==============================================================================
-- TASK 1: TMS-ATM High-Risk Transaction Monitoring Alert Logic (T-SQL / MS SQL Server)
-- ==============================================================================
-- Card Providers: VISA, PineLabs, Vegapay
-- ATM MCCs: 6011 (Automated Cash), 6010 (Manual Cash), 6050 (Quasi-Cash), 6051 (Foreign Currency / Money Orders)
-- Alert Rule: Transaction Frequency > 3 AND Total USD Equivalent > $1500 per individual per day.
-- Output: Flagged individuals (+1 Alert with Date) and their unmodified raw transaction records.
-- ==============================================================================

-- ==============================================================================
-- 1. VISA SPEND TABLE
-- ==============================================================================
-- Assumed Table: [dbo].[visa_spend]
-- Target Date Parameter (ISO YYYY-MM-DD):
DECLARE @VisaTargetDate VARCHAR(10) = '2026-09-30';

-- Query 1A: Flagged Individuals Alert Summary
WITH VisaAtmFiltered AS (
    SELECT 
        spacct,
        spname,
        spbusd,
        TRY_CAST(spmusa AS DECIMAL(18, 2)) AS usd_amount
    FROM [dbo].[visa_spend]
    WHERE spbusd = @VisaTargetDate
      AND spmcat IN ('6011', '6010', '6050', '6051')
),
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
SELECT * FROM VisaFlaggedIndividuals
ORDER BY total_usd_equivalent DESC;

-- Query 1B: Retrieve Full Unmodified Transactions for Flagged Individuals
WITH VisaFlaggedList AS (
    SELECT spacct
    FROM [dbo].[visa_spend]
    WHERE spbusd = @VisaTargetDate
      AND spmcat IN ('6011', '6010', '6050', '6051')
    GROUP BY spacct
    HAVING COUNT(*) > 3 
       AND SUM(TRY_CAST(spmusa AS DECIMAL(18, 2))) > 1500.00
)
SELECT v.*
FROM [dbo].[visa_spend] v
INNER JOIN VisaFlaggedList f ON v.spacct = f.spacct
WHERE v.spbusd = @VisaTargetDate
  AND v.spmcat IN ('6011', '6010', '6050', '6051')
ORDER BY v.spacct, v.sptime;


-- ==============================================================================
-- 2. PINELABS SPEND TABLE
-- ==============================================================================
-- Assumed Table: [dbo].[pinelabs_spend]
-- Value Date format: 'DD/MM/YYYY HH:MM:SS' or 'YYYY-MM-DD'
DECLARE @PineLabsTargetDate VARCHAR(10) = '2026-09-28';

-- Query 2A: Flagged Individuals Alert Summary
WITH PineAtmFiltered AS (
    SELECT 
        [Wallet Number] AS wallet_number,
        [Device Number] AS device_number,
        CONVERT(VARCHAR(10), TRY_CONVERT(DATETIME, [Value Date], 103), 120) AS value_date_normalized,
        TRY_CAST([Billing Amount] AS DECIMAL(18, 2)) AS usd_amount
    FROM [dbo].[pinelabs_spend]
    WHERE CONVERT(VARCHAR(10), TRY_CONVERT(DATETIME, [Value Date], 103), 120) = @PineLabsTargetDate
      AND LEFT(LTRIM(RTRIM([mcc])), 4) IN ('6011', '6010', '6050', '6051')
),
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

-- Query 2B: Retrieve Full Unmodified Transactions for Flagged Individuals
WITH PineFlaggedList AS (
    SELECT [Wallet Number] AS wallet_number
    FROM [dbo].[pinelabs_spend]
    WHERE CONVERT(VARCHAR(10), TRY_CONVERT(DATETIME, [Value Date], 103), 120) = @PineLabsTargetDate
      AND LEFT(LTRIM(RTRIM([mcc])), 4) IN ('6011', '6010', '6050', '6051')
    GROUP BY [Wallet Number]
    HAVING COUNT(*) > 3 
       AND SUM(TRY_CAST([Billing Amount] AS DECIMAL(18, 2))) > 1500.00
)
SELECT p.*
FROM [dbo].[pinelabs_spend] p
INNER JOIN PineFlaggedList f ON p.[Wallet Number] = f.wallet_number
WHERE CONVERT(VARCHAR(10), TRY_CONVERT(DATETIME, p.[Value Date], 103), 120) = @PineLabsTargetDate
  AND LEFT(LTRIM(RTRIM(p.[mcc])), 4) IN ('6011', '6010', '6050', '6051')
ORDER BY p.[Wallet Number], p.[Transaction Date];


-- ==============================================================================
-- 3. VEGAPAY SPEND TABLE
-- ==============================================================================
-- Assumed Table: [dbo].[vegapay_spend]
-- Business Date format: 'YYYY-MM-DD'
DECLARE @VegapayTargetDate VARCHAR(10) = '2026-10-11';

-- Query 3A: Flagged Individuals Alert Summary
WITH VegapayAtmFiltered AS (
    SELECT 
        [Account Number] AS account_number,
        [Customer ID] AS customer_id,
        [Card Holder Name] AS cardholder_name,
        [Business Date] AS business_date,
        TRY_CAST([Billing Amount] AS DECIMAL(18, 2)) AS usd_amount
    FROM [dbo].[vegapay_spend]
    WHERE [Business Date] = @VegapayTargetDate
      AND CAST([MCC] AS VARCHAR(10)) IN ('6011', '6010', '6050', '6051')
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

-- Query 3B: Retrieve Full Unmodified Transactions for Flagged Individuals
WITH VegapayFlaggedList AS (
    SELECT [Account Number] AS account_number
    FROM [dbo].[vegapay_spend]
    WHERE [Business Date] = @VegapayTargetDate
      AND CAST([MCC] AS VARCHAR(10)) IN ('6011', '6010', '6050', '6051')
    GROUP BY [Account Number]
    HAVING COUNT(*) > 3 
       AND SUM(TRY_CAST([Billing Amount] AS DECIMAL(18, 2))) > 1500.00
)
SELECT vg.*
FROM [dbo].[vegapay_spend] vg
INNER JOIN VegapayFlaggedList f ON vg.[Account Number] = f.account_number
WHERE vg.[Business Date] = @VegapayTargetDate
  AND CAST(vg.[MCC] AS VARCHAR(10)) IN ('6011', '6010', '6050', '6051')
ORDER BY vg.[Account Number], vg.[Transaction Date];

