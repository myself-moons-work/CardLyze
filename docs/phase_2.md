Read SPEC.md first. This phase is backend logic only (no UI): card definitions and the column-addition service.

1. app/cards.py: define the three cards (visa, pinelabs, vegapay) as data. Copy the column lists exactly, in order, from /reference/Card_Data.ipynb and cross-check them against /reference/Transaction_Data_Dictionary.docx. Expected counts: VISA 29, PineLabs 68, Vegapay 61. For each card include:
   - key, label, expected_columns
   - numeric_cols and date_cols (take them from the Data Analysis section of the notebook). date_cols maps column -> a LIST of explicit candidate formats. Do not use pandas format guessing, because dd/mm vs mm/dd is ambiguous. Starting formats from the data dictionary samples (mark them in comments as "confirm against real data"):
       VISA: spbusd %Y-%m-%d; spdate %d%m%Y
       PineLabs: Value Date and Transaction Date %d/%m/%Y %H:%M:%S (also try %d/%m/%Y)
       Vegapay: Business Date %Y-%m-%d; DOB %d-%m-%Y; Mastercard Date %d-%m-%Y; Transaction Date %d-%m-%Y; Settlement Date %Y-%m-%d
   - id_like_cols that must always stay text (card numbers, account IDs, codes with leading zeros such as VISA spcati and Vegapay Transaction Code)
   - mcc_col: VISA spmcat, PineLabs mcc, Vegapay MCC
   - country rule: Vegapay uses the existing "Merchant Country" column. VISA has no country column, so derive a 2-letter country code from the last token of spldes (sample: "CHOPSTIX BEACONSFIELD GB"). PineLabs has no country column, so try the last 2-letter uppercase token of "Merchant Name & Location" and otherwise "Unknown". Implement as a derive_country(df, card) function that returns a new column named country_code. Add a clear comment that VISA and PineLabs rules are assumptions to confirm.
   - sensitive_cols hidden by default in the UI (for Vegapay: Passport Number, DOB; propose others) and key_cols (the default visible columns for analysis: propose 10 to 14 sensible ones per card; I will review).
2. app/services/headers.py:
   - read_excel_bytes(data: bytes, header) using dtype=str, engine python-calamine if installed else openpyxl, never touching disk.
   - add_headers(data: bytes, card) -> result with: ok flag, DataFrame (only if ok), rows, found_columns, expected_columns, and a human-readable message. Behaviour from the notebook: read with header=None, dtype=str, drop rows where all cells are empty, reset index, compare column count, assign names only on match. On mismatch return a clear error (found vs expected) and no data. Also detect the case where the first row already equals the expected column names (file already has headers) and say so.
   - to_xlsx_bytes(df) -> bytes via BytesIO, index=False.
3. Tests (pytest, synthetic data only, built in memory with openpyxl; never use real data and never commit data files): correct column count succeeds; extra or missing column fails with the right message; all-empty rows dropped; leading zeros preserved ("00000003" stays "00000003"); already-has-headers detected; export round-trip keeps values and header order; cards config sanity (counts 29/68/61, no duplicate names, every numeric/date/mcc/key/sensitive column exists in expected_columns); derive_country cases for each card including missing and odd values.

Run pytest and show results. Stop with a summary.