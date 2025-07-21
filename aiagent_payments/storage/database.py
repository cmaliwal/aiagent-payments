"""
SQLite database storage backend for production use.
"""

import json
import logging
import sqlite3
from datetime import datetime
from decimal import Decimal
from enum import Enum

from ..exceptions import StorageError, ValidationError
from ..models import PaymentPlan, PaymentTransaction, Subscription, UsageRecord
from ..utils import retry
from .base import StorageBackend

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal objects."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class DatabaseStorage(StorageBackend):
    """
    SQLite database storage backend for production use.
    """

    def __init__(self, db_path: str = "aiagent_payments.db"):
        self.db_path = db_path
        super().__init__("DatabaseStorage")
        self._init_database()
        logger.info("DatabaseStorage initialized with database: %s", db_path)

    def _get_capabilities(self):
        """
        Get the capabilities of this storage backend.
        Returns:
            StorageCapabilities object describing supported features
        """
        from .base import StorageCapabilities

        return StorageCapabilities(
            supports_transactions=True,
            supports_encryption=False,
            supports_backup=True,
            supports_search=True,
            supports_indexing=True,
            max_data_size=1024 * 1024 * 1024,  # 1 GB
            supports_concurrent_access=True,
            supports_pagination=True,
            supports_bulk_operations=True,
        )

    def _validate_configuration(self):
        """
        Validate the storage backend configuration.
        Raises:
            ConfigurationError: If the configuration is invalid
        """
        if not self.db_path or not isinstance(self.db_path, str):
            from ..exceptions import ConfigurationError

            raise ConfigurationError("db_path is required for DatabaseStorage.")
        # Optionally check if the file is writable
        try:
            with open(self.db_path, "a"):
                pass
        except Exception as e:
            from ..exceptions import ConfigurationError

            raise ConfigurationError(f"Database file {self.db_path} is not writable: {e}")

    def _perform_health_check(self):
        """
        Perform a health check for the DatabaseStorage backend.
        Raises:
            Exception: If the health check fails
        """
        try:
            # Try to connect and execute a simple query
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("SELECT 1")
        except Exception as e:
            raise Exception(f"DatabaseStorage health check failed: {e}")

    def _init_database(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS payment_plans (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        payment_type TEXT NOT NULL,
                        price REAL NOT NULL,
                        currency TEXT DEFAULT 'USD',
                        price_per_request REAL,
                        billing_period TEXT,
                        requests_per_period INTEGER,
                        free_requests INTEGER DEFAULT 0,
                        features TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TEXT NOT NULL
                    )
                """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        plan_id TEXT NOT NULL,
                        status TEXT DEFAULT 'active',
                        start_date TEXT NOT NULL,
                        end_date TEXT,
                        current_period_start TEXT,
                        current_period_end TEXT,
                        usage_count INTEGER DEFAULT 0,
                        metadata TEXT
                    )
                """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS usage_records (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        feature TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        cost REAL,
                        currency TEXT DEFAULT 'USD',
                        metadata TEXT
                    )
                """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS transactions (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        amount REAL NOT NULL,
                        currency TEXT DEFAULT 'USD',
                        payment_method TEXT DEFAULT 'unknown',
                        status TEXT DEFAULT 'pending',
                        created_at TEXT NOT NULL,
                        completed_at TEXT,
                        metadata TEXT
                    )
                """
                )
                conn.commit()
            logger.info("Database tables initialized successfully")
        except sqlite3.Error as e:
            logger.error("Error initializing database: %s", str(e))
            raise StorageError(f"Failed to initialize database: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying DB save...")
    def save_payment_plan(self, plan: PaymentPlan) -> None:
        if not plan or not isinstance(plan, PaymentPlan):
            raise ValidationError("Invalid payment plan object", field="plan", value=plan)

        # Validate data size before saving
        self._validate_and_save_data(plan)

        # Use transaction for atomic operation
        def save_plan_operation(conn):
            payment_type = plan.payment_type.value if isinstance(plan.payment_type, Enum) else str(plan.payment_type)
            billing_period = (
                plan.billing_period.value
                if plan.billing_period and isinstance(plan.billing_period, Enum)
                else (str(plan.billing_period) if plan.billing_period else None)
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO payment_plans
                (id, name, description, payment_type, price, currency, price_per_request,
                billing_period, requests_per_period, free_requests, features, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    plan.id,
                    plan.name,
                    plan.description,
                    payment_type,
                    plan.price,
                    plan.currency,
                    plan.price_per_request,
                    billing_period,
                    plan.requests_per_period,
                    plan.free_requests,
                    json.dumps(plan.features, cls=DecimalEncoder),
                    plan.is_active,
                    plan.created_at.isoformat(),
                ),
            )

        self._save_with_transaction(f"save_payment_plan({plan.id})", save_plan_operation)
        logger.info("Saved payment plan: %s", plan.id)

    def list_payment_plans(self) -> list[PaymentPlan]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT * FROM payment_plans WHERE is_active = 1")
                plans = []
                for row in cursor.fetchall():
                    try:
                        plan = PaymentPlan(
                            id=row[0],
                            name=row[1],
                            description=row[2],
                            payment_type=row[3],
                            price=row[4],
                            currency=row[5],
                            price_per_request=row[6],
                            billing_period=row[7],
                            requests_per_period=row[8],
                            free_requests=row[9],
                            features=json.loads(row[10]) if row[10] else [],
                            is_active=bool(row[11]),
                            created_at=datetime.fromisoformat(row[12]),
                        )
                        plans.append(plan)
                    except Exception as e:
                        logger.error("Error deserializing payment plan: %s", str(e))
                logger.debug("Retrieved %d active payment plans", len(plans))
                return plans
        except sqlite3.Error as e:
            logger.error("Error listing payment plans: %s", str(e))
            return []

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying DB save...")
    def save_subscription(self, subscription: Subscription) -> None:
        if not subscription or not isinstance(subscription, Subscription):
            raise ValidationError("Invalid subscription object", field="subscription", value=subscription)

        # Validate data size before saving
        self._validate_and_save_data(subscription)

        # Use transaction for atomic operation
        def save_subscription_operation(conn):
            conn.execute(
                """
                INSERT OR REPLACE INTO subscriptions
                (id, user_id, plan_id, status, start_date, end_date,
                 current_period_start, current_period_end, usage_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    subscription.id,
                    subscription.user_id,
                    subscription.plan_id,
                    subscription.status,
                    subscription.start_date.isoformat(),
                    (subscription.end_date.isoformat() if subscription.end_date else None),
                    (subscription.current_period_start.isoformat() if subscription.current_period_start else None),
                    (subscription.current_period_end.isoformat() if subscription.current_period_end else None),
                    subscription.usage_count,
                    json.dumps(subscription.metadata, cls=DecimalEncoder),
                ),
            )

        self._save_with_transaction(f"save_subscription({subscription.id})", save_subscription_operation)
        logger.info(
            "Saved subscription: %s for user: %s",
            subscription.id,
            subscription.user_id,
        )

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying DB read...")
    def get_subscription(self, subscription_id: str) -> Subscription | None:
        if not subscription_id or not isinstance(subscription_id, str):
            raise ValidationError(
                "Invalid subscription_id",
                field="subscription_id",
                value=subscription_id,
            )
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT * FROM subscriptions WHERE id = ?
                """,
                    (subscription_id,),
                )
                row = cursor.fetchone()
                if row:
                    subscription = Subscription(
                        id=row[0],
                        user_id=row[1],
                        plan_id=row[2],
                        status=row[3],
                        start_date=datetime.fromisoformat(row[4]),
                        end_date=datetime.fromisoformat(row[5]) if row[5] else None,
                        current_period_start=(datetime.fromisoformat(row[6]) if row[6] else None),
                        current_period_end=(datetime.fromisoformat(row[7]) if row[7] else None),
                        usage_count=row[8],
                        metadata=json.loads(row[9]) if row[9] else {},
                    )
                    logger.debug("Retrieved subscription: %s", subscription_id)
                    return subscription
        except sqlite3.Error as e:
            logger.error("Error retrieving subscription %s: %s", subscription_id, str(e))
        except Exception as e:
            logger.error("Error deserializing subscription %s: %s", subscription_id, str(e))
        logger.debug("Subscription not found: %s", subscription_id)
        return None

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying DB read...")
    def get_user_subscription(self, user_id: str) -> Subscription | None:
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("Invalid user_id", field="user_id", value=user_id)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT * FROM subscriptions
                    WHERE user_id = ? AND status = 'active'
                    ORDER BY start_date DESC LIMIT 1
                """,
                    (user_id,),
                )
                row = cursor.fetchone()
                if row:
                    subscription = Subscription(
                        id=row[0],
                        user_id=row[1],
                        plan_id=row[2],
                        status=row[3],
                        start_date=datetime.fromisoformat(row[4]),
                        end_date=datetime.fromisoformat(row[5]) if row[5] else None,
                        current_period_start=(datetime.fromisoformat(row[6]) if row[6] else None),
                        current_period_end=(datetime.fromisoformat(row[7]) if row[7] else None),
                        usage_count=row[8],
                        metadata=json.loads(row[9]) if row[9] else {},
                    )
                    logger.debug(
                        "Retrieved active subscription for user %s: %s",
                        user_id,
                        subscription.id,
                    )
                    return subscription
        except sqlite3.Error as e:
            logger.error("Error retrieving user subscription for %s: %s", user_id, str(e))
        except Exception as e:
            logger.error("Error deserializing user subscription for %s: %s", user_id, str(e))
        logger.debug("No active subscription found for user: %s", user_id)
        return None

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying DB save...")
    def save_usage_record(self, record: UsageRecord) -> None:
        if not record or not isinstance(record, UsageRecord):
            raise ValidationError("Invalid usage record object", field="record", value=record)

        # Validate data size before saving
        self._validate_and_save_data(record)

        # Use transaction for atomic operation
        def save_usage_record_operation(conn):
            conn.execute(
                """
                INSERT INTO usage_records
                (id, user_id, feature, timestamp, cost, currency, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record.id,
                    record.user_id,
                    record.feature,
                    record.timestamp.isoformat(),
                    record.cost,
                    record.currency,
                    json.dumps(record.metadata, cls=DecimalEncoder),
                ),
            )

        self._save_with_transaction(f"save_usage_record({record.id})", save_usage_record_operation)
        logger.debug(
            "Saved usage record: %s for user: %s, feature: %s",
            record.id,
            record.user_id,
            record.feature,
        )

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying DB save...")
    def save_transaction(self, transaction: PaymentTransaction) -> None:
        if not transaction or not isinstance(transaction, PaymentTransaction):
            raise ValidationError("Invalid transaction object", field="transaction", value=transaction)

        # Validate data size before saving
        self._validate_and_save_data(transaction)

        # Use transaction for atomic operation
        def save_transaction_operation(conn):
            try:
                conn.execute(
                    """
                    INSERT INTO transactions
                    (id, user_id, amount, currency, payment_method, status, created_at, completed_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        transaction.id,
                        transaction.user_id,
                        transaction.amount,
                        transaction.currency,
                        transaction.payment_method,
                        transaction.status,
                        transaction.created_at.isoformat(),
                        (transaction.completed_at.isoformat() if transaction.completed_at else None),
                        json.dumps(transaction.metadata, cls=DecimalEncoder),
                    ),
                )
            except sqlite3.IntegrityError as e:
                # Surface duplicate transaction ID as a real error (do not overwrite)
                raise StorageError(f"Transaction ID {transaction.id} already exists: {e}")

        self._save_with_transaction(f"save_transaction({transaction.id})", save_transaction_operation)
        logger.debug(
            "Saved transaction: %s for user: %s, amount: %.2f",
            transaction.id,
            transaction.user_id,
            transaction.amount,
        )

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying DB read...")
    def get_payment_plan(self, plan_id: str) -> PaymentPlan | None:
        if not plan_id or not isinstance(plan_id, str):
            raise ValidationError("Invalid plan_id", field="plan_id", value=plan_id)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT * FROM payment_plans WHERE id = ?", (plan_id,))
                row = cursor.fetchone()
                if row:
                    try:
                        plan = PaymentPlan(
                            id=row[0],
                            name=row[1],
                            description=row[2],
                            payment_type=row[3],
                            price=row[4],
                            currency=row[5],
                            price_per_request=row[6],
                            billing_period=row[7],
                            requests_per_period=row[8],
                            free_requests=row[9],
                            features=json.loads(row[10]) if row[10] else [],
                            is_active=bool(row[11]),
                            created_at=datetime.fromisoformat(row[12]),
                        )
                        logger.debug("Retrieved payment plan: %s", plan_id)
                        return plan
                    except Exception as e:
                        logger.error("Error deserializing payment plan %s: %s", plan_id, str(e))
                        return None
                logger.debug("Payment plan not found: %s", plan_id)
                return None
        except sqlite3.Error as e:
            logger.error("Error reading payment plan: %s", str(e))
            raise StorageError(f"Failed to read payment plan: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying DB read...")
    def get_transaction(self, transaction_id: str) -> PaymentTransaction | None:
        if not transaction_id or not isinstance(transaction_id, str):
            raise ValidationError("Invalid transaction_id", field="transaction_id", value=transaction_id)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
                row = cursor.fetchone()
                if row:
                    try:
                        transaction = PaymentTransaction(
                            id=row[0],
                            user_id=row[1],
                            amount=row[2],
                            currency=row[3],
                            payment_method=row[4],
                            status=row[5],
                            created_at=datetime.fromisoformat(row[6]),
                            completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
                            metadata=json.loads(row[8]) if row[8] else {},
                        )
                        logger.debug("Retrieved transaction: %s", transaction_id)
                        return transaction
                    except Exception as e:
                        logger.error("Error deserializing transaction %s: %s", transaction_id, str(e))
                        return None
                logger.debug("Transaction not found: %s", transaction_id)
                return None
        except sqlite3.Error as e:
            logger.error("Error reading transaction: %s", str(e))
            raise StorageError(f"Failed to read transaction: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying DB read...")
    def get_user_usage(
        self, user_id: str, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> list[UsageRecord]:
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("Invalid user_id", field="user_id", value=user_id)
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = "SELECT * FROM usage_records WHERE user_id = ?"
                params = [user_id]
                records = []
                for row in conn.execute(query, params):
                    try:
                        record = UsageRecord(
                            id=row[0],
                            user_id=row[1],
                            feature=row[2],
                            timestamp=datetime.fromisoformat(row[3]),
                            cost=row[4],
                            currency=row[5],
                            metadata=json.loads(row[6]) if row[6] else {},
                        )
                        if start_date and record.timestamp < start_date:
                            continue
                        if end_date and record.timestamp > end_date:
                            continue
                        records.append(record)
                    except Exception as e:
                        logger.error("Error deserializing usage record: %s", str(e))
                filtered_records = sorted(records, key=lambda x: x.timestamp)
                logger.debug("Retrieved %d usage records for user %s", len(filtered_records), user_id)
                return filtered_records
        except sqlite3.Error as e:
            logger.error("Error reading usage records: %s", str(e))
            raise StorageError(f"Failed to read usage records: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying DB read...")
    def get_transactions_by_user_id(self, user_id: str) -> list[PaymentTransaction]:
        """
        Retrieve all transactions for a specific user.

        Args:
            user_id: ID of the user

        Returns:
            List of PaymentTransaction objects for the user

        Raises:
            ValidationError: If the user_id is invalid
        """
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("Invalid user_id", field="user_id", value=user_id)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
                transactions = []
                for row in cursor.fetchall():
                    try:
                        transaction = PaymentTransaction(
                            id=row[0],
                            user_id=row[1],
                            amount=row[2],
                            currency=row[3],
                            payment_method=row[4],
                            status=row[5],
                            created_at=datetime.fromisoformat(row[6]),
                            completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
                            metadata=json.loads(row[8]) if row[8] else {},
                        )
                        transactions.append(transaction)
                    except Exception as e:
                        logger.error("Error deserializing transaction: %s", str(e))
                logger.debug("Retrieved %d transactions for user %s", len(transactions), user_id)
                return transactions
        except sqlite3.Error as e:
            logger.error("Error reading transactions for user %s: %s", user_id, str(e))
            raise StorageError(f"Failed to read transactions: {str(e)}")

    def begin_transaction(self) -> sqlite3.Connection:
        """
        Begin a SQLite transaction for atomic operations.

        Returns:
            sqlite3.Connection: Database connection with active transaction

        Raises:
            StorageError: If transaction cannot be started
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("BEGIN TRANSACTION")
            logger.debug("Started database transaction")
            return conn
        except sqlite3.Error as e:
            logger.error("Failed to begin transaction: %s", str(e))
            raise StorageError(f"Failed to begin transaction: {str(e)}")

    def _save_with_transaction(self, operation_name: str, operation_func):
        """
        Execute a save operation within a transaction for atomicity.

        Args:
            operation_name: Name of the operation for logging
            operation_func: Function that performs the database operation

        Raises:
            StorageError: If the transaction fails
        """
        conn = None
        try:
            conn = self.begin_transaction()
            operation_func(conn)
            conn.commit()
            logger.debug("Committed transaction for %s", operation_name)
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                    logger.debug("Rolled back transaction for %s", operation_name)
                except sqlite3.Error as rollback_error:
                    logger.error("Failed to rollback transaction: %s", str(rollback_error))
            logger.error("Transaction failed for %s: %s", operation_name, str(e))
            raise StorageError(f"Transaction failed for {operation_name}: {str(e)}")
        finally:
            if conn:
                conn.close()

    def commit(self):
        """Commit the current transaction (no-op for DatabaseStorage since we use _save_with_transaction)."""
        # DatabaseStorage handles transactions internally through _save_with_transaction
        # This method exists for compatibility with providers that expect explicit transaction control
        pass

    def rollback(self):
        """Rollback the current transaction (no-op for DatabaseStorage since we use _save_with_transaction)."""
        # DatabaseStorage handles transactions internally through _save_with_transaction
        # This method exists for compatibility with providers that expect explicit transaction control
        pass

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying DB read...")
    def list_transactions(
        self, user_id: str | None = None, status: str | None = None, limit: int | None = None
    ) -> list[PaymentTransaction]:
        """
        List transactions with optional filtering.

        Args:
            user_id: Optional user ID to filter by
            status: Optional status to filter by
            limit: Optional limit on number of transactions to return

        Returns:
            List of PaymentTransaction objects matching the filters
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = "SELECT * FROM transactions WHERE 1=1"
                params = []

                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)
                if status:
                    query += " AND status = ?"
                    params.append(status)

                query += " ORDER BY created_at DESC"

                if limit:
                    query += " LIMIT ?"
                    params.append(limit)

                cursor = conn.execute(query, params)
                transactions = []
                for row in cursor.fetchall():
                    try:
                        transaction = PaymentTransaction(
                            id=row[0],
                            user_id=row[1],
                            amount=row[2],
                            currency=row[3],
                            payment_method=row[4],
                            status=row[5],
                            created_at=datetime.fromisoformat(row[6]),
                            completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
                            metadata=json.loads(row[8]) if row[8] else {},
                        )
                        transactions.append(transaction)
                    except Exception as e:
                        logger.error("Error deserializing transaction: %s", str(e))

                logger.debug(
                    "Retrieved %d transactions with filters: user_id=%s, status=%s, limit=%s",
                    len(transactions),
                    user_id,
                    status,
                    limit,
                )
                return transactions
        except sqlite3.Error as e:
            logger.error("Error reading transactions: %s", str(e))
            raise StorageError(f"Failed to read transactions: {str(e)}")

    def update_transaction(self, transaction: PaymentTransaction) -> None:
        """
        Update an existing payment transaction in the database.

        Args:
            transaction: PaymentTransaction object to update

        Raises:
            ValidationError: If the transaction is invalid
            StorageError: If the transaction does not exist
        """
        if not transaction or not isinstance(transaction, PaymentTransaction):
            raise ValidationError("Invalid transaction object", field="transaction", value=transaction)
        self._validate_and_save_data(transaction)

        def update_transaction_operation(conn):
            cursor = conn.execute("SELECT 1 FROM transactions WHERE id = ?", (transaction.id,))
            if cursor.fetchone() is None:
                raise StorageError(f"Transaction with id {transaction.id} does not exist")
            conn.execute(
                """
                UPDATE transactions SET
                    user_id = ?,
                    amount = ?,
                    currency = ?,
                    payment_method = ?,
                    status = ?,
                    created_at = ?,
                    completed_at = ?,
                    metadata = ?
                WHERE id = ?
                """,
                (
                    transaction.user_id,
                    transaction.amount,
                    transaction.currency,
                    transaction.payment_method,
                    transaction.status,
                    transaction.created_at.isoformat(),
                    (transaction.completed_at.isoformat() if transaction.completed_at else None),
                    json.dumps(transaction.metadata, cls=DecimalEncoder),
                    transaction.id,
                ),
            )

        self._save_with_transaction(f"update_transaction({transaction.id})", update_transaction_operation)
        logger.debug(
            "Updated transaction: %s for user: %s, amount: %.2f",
            transaction.id,
            transaction.user_id,
            transaction.amount,
        )
