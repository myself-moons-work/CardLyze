"""Data Access Layer (Repository Pattern) for CardLyze TMS-ATM.

Provides an abstracted data interface allowing the report engine to query either:
1. FileSimulationProvider: Reads daily/monthly Excel files locally.
2. SQLDatabaseProvider: Connects to AWS RDS MS SQL Server via pyodbc/SQLAlchemy.
"""

from abc import ABC, abstractmethod
import glob
import logging
import os
import re
from typing import Dict, List, Optional
import pandas as pd

from app.cards import CARDS
from app.config import settings

logger = logging.getLogger(__name__)


class TransactionDataProvider(ABC):
    """Abstract base class for querying card transactions."""

    @abstractmethod
    def get_daily_transactions(self, card_key: str, target_date: str) -> pd.DataFrame:
        """Fetch all raw transactions for a card provider on a specific date (YYYY-MM-DD)."""
        pass

    @abstractmethod
    def get_individual_history(self, card_key: str, account_number: str) -> pd.DataFrame:
        """Fetch all historical transactions for a specific individual/account."""
        pass

    @abstractmethod
    def get_available_dates(self, card_key: str) -> List[str]:
        """Return a sorted descending list of all available transaction dates (YYYY-MM-DD)."""
        pass


class FileSimulationProvider(TransactionDataProvider):
    """Simulates database queries by reading local daily and monthly Excel files."""

    def __init__(
        self,
        input_files_dir: Optional[str] = None,
        monthly_files_dir: str = "data_with_headers",
    ):
        self.input_files_dir = input_files_dir or settings.INPUT_FILES_DIR
        self.monthly_files_dir = monthly_files_dir

    def _get_daily_file_path(self, card_key: str, target_date: str) -> str:
        card = card_key.lower().strip()
        return os.path.join(self.input_files_dir, f"{card}_{target_date}.xlsx")

    def _get_monthly_file_path(self, card_key: str) -> Optional[str]:
        card = card_key.lower().strip()
        pattern = os.path.join(self.monthly_files_dir, f"{card}_with_headers_*.xlsx")
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
        # Fallback to data/ only if using default monthly directory
        if self.monthly_files_dir == "data_with_headers":
            pattern_data = os.path.join("data", f"*{card}*.xlsx")
            matches_data = glob.glob(pattern_data)
            return matches_data[0] if matches_data else None
        return None

    def get_daily_transactions(self, card_key: str, target_date: str) -> pd.DataFrame:
        card = card_key.lower().strip()
        file_path = self._get_daily_file_path(card, target_date)
        if not os.path.exists(file_path):
            logger.info("Daily file not found: %s", file_path)
            # Return empty DataFrame with expected columns
            expected = CARDS.get(card)
            cols = expected.expected_columns if expected else []
            return pd.DataFrame(columns=cols)

        try:
            # Calamine engine provides high-speed Excel parsing
            df = pd.read_excel(file_path, dtype=str, engine="calamine")
            df.columns = [str(c).strip() for c in df.columns]
            return df
        except Exception as e:
            logger.error("Failed to read daily file %s: %s", file_path, e)
            return pd.DataFrame()

    def get_individual_history(self, card_key: str, account_number: str) -> pd.DataFrame:
        card = card_key.lower().strip()
        acct_clean = str(account_number).strip()

        # Identify account column name
        if card == "visa":
            acct_col = "spacct"
        elif card == "pinelabs":
            acct_col = "Wallet Number"
        elif card == "vegapay":
            acct_col = "Account Number"
        else:
            raise ValueError(f"Unknown card provider: {card_key}")

        # Try fast lookup from monthly file if present
        monthly_path = self._get_monthly_file_path(card)
        if monthly_path and os.path.exists(monthly_path):
            try:
                df = pd.read_excel(monthly_path, dtype=str, engine="calamine")
                df.columns = [str(c).strip() for c in df.columns]
                if acct_col in df.columns:
                    mask = df[acct_col].fillna("").astype(str).str.strip() == acct_clean
                    sub = df[mask].copy()
                    if len(sub) > 0:
                        return sub
            except Exception as e:
                logger.warning("Could not read monthly file %s for history: %s", monthly_path, e)

        # Fallback: Scan through all daily files for this card
        pattern = os.path.join(self.input_files_dir, f"{card}_*.xlsx")
        daily_files = sorted(glob.glob(pattern))
        history_frames = []

        for fpath in daily_files:
            try:
                df = pd.read_excel(fpath, dtype=str, engine="calamine")
                df.columns = [str(c).strip() for c in df.columns]
                if acct_col in df.columns:
                    sub = df[df[acct_col].fillna("").astype(str).str.strip() == acct_clean]
                    if len(sub) > 0:
                        history_frames.append(sub)
            except Exception as e:
                logger.warning("Error reading %s during history search: %s", fpath, e)

        if history_frames:
            return pd.concat(history_frames, ignore_index=True)

        expected = CARDS.get(card)
        cols = expected.expected_columns if expected else []
        return pd.DataFrame(columns=cols)

    def get_available_dates(self, card_key: str) -> List[str]:
        card = card_key.lower().strip()
        pattern = os.path.join(self.input_files_dir, f"{card}_*.xlsx")
        files = glob.glob(pattern)
        dates = []
        date_pattern = re.compile(rf"{card}_(\d{{4}}-\d{{2}}-\d{{2}})\.xlsx$", re.IGNORECASE)
        for f in files:
            m = date_pattern.search(os.path.basename(f))
            if m:
                dates.append(m.group(1))
        dates.sort(reverse=True)
        return dates


class SQLDatabaseProvider(TransactionDataProvider):
    """Executes validated T-SQL queries against AWS RDS MS SQL Server."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        driver: Optional[str] = None,
    ):
        self.host = host or settings.DB_HOST
        self.port = port or settings.DB_PORT
        self.database = database or settings.DB_NAME
        self.username = username or settings.DB_USER
        self.password = password or settings.DB_PASSWORD
        self.driver = driver or settings.DB_DRIVER
        self._engine = None

    def _get_connection_string(self) -> str:
        # Standard SQLAlchemy connection string for MS SQL Server via pyodbc
        return (
            f"mssql+pyodbc://{self.username}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}?"
            f"driver={self.driver.replace(' ', '+')}&TrustServerCertificate=yes"
        )

    def _get_engine(self):
        if self._engine is None:
            try:
                from sqlalchemy import create_engine
                self._engine = create_engine(self._get_connection_string())
            except Exception as e:
                logger.error("Failed to initialize database engine: %s", e)
                raise ConnectionError(
                    f"Could not connect to MS SQL Server at {self.host}:{self.port}. "
                    f"Ensure OpenVPN is connected and credentials are correct. Error: {e}"
                )
        return self._engine

    def get_daily_transactions(self, card_key: str, target_date: str) -> pd.DataFrame:
        card = card_key.lower().strip()
        engine = self._get_engine()

        # Table names & column mapping aligned with task_1/tms_atm_task1_queries.sql
        if card == "visa":
            table = "[dbo].[visa_spend]"
            date_col = "spdate"
            query = f"""
            SELECT * FROM {table}
            WHERE COALESCE(
                TRY_CONVERT(DATE, 
                    LEFT(RIGHT('00000000' + LTRIM(RTRIM(CAST({date_col} AS VARCHAR(8)))), 8), 2) + '/' +
                    SUBSTRING(RIGHT('00000000' + LTRIM(RTRIM(CAST({date_col} AS VARCHAR(8)))), 8), 3, 2) + '/' +
                    RIGHT(RIGHT('00000000' + LTRIM(RTRIM(CAST({date_col} AS VARCHAR(8)))), 8), 4), 103),
                TRY_CONVERT(DATE, {date_col}, 120),
                TRY_CONVERT(DATE, {date_col})
            ) = :target_date
            """
        elif card == "pinelabs":
            table = "[dbo].[pinelabs_spend]"
            date_col = "[Transaction Date]"
            query = f"""
            SELECT * FROM {table}
            WHERE COALESCE(
                TRY_CONVERT(DATE, {date_col}, 103),
                TRY_CONVERT(DATE, {date_col}, 120),
                TRY_CONVERT(DATE, {date_col})
            ) = :target_date
            """
        elif card == "vegapay":
            table = "[dbo].[vegapay_spend]"
            date_col = "[Transaction Date]"
            query = f"""
            SELECT * FROM {table}
            WHERE COALESCE(
                TRY_CONVERT(DATE, {date_col}, 105),
                TRY_CONVERT(DATE, {date_col}, 120),
                TRY_CONVERT(DATE, {date_col})
            ) = :target_date
            """
        else:
            raise ValueError(f"Unknown card key: {card_key}")

        return pd.read_sql(query, engine, params={"target_date": target_date})

    def get_individual_history(self, card_key: str, account_number: str) -> pd.DataFrame:
        card = card_key.lower().strip()
        engine = self._get_engine()

        if card == "visa":
            table = "[dbo].[visa_spend]"
            acct_col = "spacct"
        elif card == "pinelabs":
            table = "[dbo].[pinelabs_spend]"
            acct_col = "[Wallet Number]"
        elif card == "vegapay":
            table = "[dbo].[vegapay_spend]"
            acct_col = "[Account Number]"
        else:
            raise ValueError(f"Unknown card key: {card_key}")

        query = f"SELECT * FROM {table} WHERE {acct_col} = :account_number"
        return pd.read_sql(query, engine, params={"account_number": str(account_number).strip()})

    def get_available_dates(self, card_key: str) -> List[str]:
        card = card_key.lower().strip()
        engine = self._get_engine()
        if card == "visa":
            table = "[dbo].[visa_spend]"
            expr = """COALESCE(
                TRY_CONVERT(DATE, 
                    LEFT(RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8), 2) + '/' +
                    SUBSTRING(RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8), 3, 2) + '/' +
                    RIGHT(RIGHT('00000000' + LTRIM(RTRIM(CAST(spdate AS VARCHAR(8)))), 8), 4), 103),
                TRY_CONVERT(DATE, spdate, 120),
                TRY_CONVERT(DATE, spdate)
            )"""
        elif card == "pinelabs":
            table = "[dbo].[pinelabs_spend]"
            expr = "COALESCE(TRY_CONVERT(DATE, [Transaction Date], 103), TRY_CONVERT(DATE, [Transaction Date]))"
        elif card == "vegapay":
            table = "[dbo].[vegapay_spend]"
            expr = "COALESCE(TRY_CONVERT(DATE, [Transaction Date], 105), TRY_CONVERT(DATE, [Transaction Date]))"
        else:
            raise ValueError(f"Unknown card key: {card_key}")

        query = f"SELECT DISTINCT CONVERT(VARCHAR(10), {expr}, 23) AS tx_date FROM {table} WHERE {expr} IS NOT NULL ORDER BY tx_date DESC"
        df = pd.read_sql(query, engine)
        return [str(d).strip() for d in df["tx_date"].tolist() if d]


def get_data_provider() -> TransactionDataProvider:
    """Factory function returning active provider based on configuration."""
    provider_type = settings.DATA_SOURCE_PROVIDER.lower().strip()
    if provider_type == "sql":
        return SQLDatabaseProvider()
    return FileSimulationProvider()
