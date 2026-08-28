"""SQL Agent engine.

Holds a demo analytics schema, introspects it, generates SQL from a natural
language question via the code-tuned model, executes it safely, and returns
the results as context for the answer.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import inspect, text

from ..core.config import get_settings
from ..core.logging import get_logger
from ..core.model_gateway import get_gateway
from ..core.model_router import ModelRouter
from ..core.schemas import Citation, SourceType, TaskType
from .database import get_session_factory

logger = get_logger("sql_engine")

FORBIDDEN = ("insert", "update", "delete", "drop", "alter", "create", "truncate", "grant")


class SQLEngine:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.gateway = get_gateway()
        self.router = ModelRouter()

    # ---------------- schema ----------------
    def schema_description(self) -> str:
        factory = get_session_factory()
        with factory() as db:
            insp = inspect(db.bind)
            lines: list[str] = []
            for table_name in ("products", "sales_orders", "sales_lines"):
                cols = insp.get_columns(table_name)
                col_desc = ", ".join(f"{c['name']} {c['type']}" for c in cols)
                lines.append(f"Table {table_name}({col_desc})")

    # ---------------- generation ----------------
    async def answer_question(self, question: str) -> Citation:
        """Generate + run SQL for a natural-language question.

        Returns a Citation with the result rows as snippet and metadata
        carrying the raw result set.
        """
        model = self.router.resolve(TaskType.SQL_GENERATION, None)
        schema = self.schema_description()
        prompt = (
            "You are a PostgreSQL analytics engine. Given the schema below, "
            "write a single read-only SELECT SQL query that answers the user's "
            "question. Output ONLY the SQL, no explanation, no markdown, no "
            "trailing semicolon.\n\n"
            f"SCHEMA:\n{schema}\n\n"
            f"QUESTION: {question}\n"
            "SQL:"
        )
        result = await self.gateway.complete(
            model,
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=600,
            task_type=TaskType.SQL_GENERATION,
            use_cache=False,
        )
        if result.error or not result.text:
            return Citation(type=SourceType.SQL, title="SQL Agent",
                            snippet=f"SQL generation failed: {result.error or 'empty'}")
        sql = self._clean_sql(result.text)
        rows, error = self._execute(sql)
        if error:
            return Citation(type=SourceType.SQL, title="SQL Agent",
                            snippet=f"Could not run query: {error}")
        snippet = rows[:800] if isinstance(rows, str) else str(rows)[:800]
        return Citation(
            type=SourceType.SQL,
            title="SQL Agent Result",
            snippet=snippet,
            metadata={"sql": sql, "question": question, "result": rows},
        )

    def _execute(self, sql: str) -> tuple[Any, Optional[str]]:
        lowered = sql.lower().strip()
        if any(f" {w} " in f" {lowered} " or lowered.startswith(w) for w in FORBIDDEN):
            return None, "Only read-only SELECT queries are allowed."
        try:
            factory = get_session_factory()
            with factory() as db:
                result = db.execute(text(sql))
                if result.returns_rows:
                    cols = result.keys()
                    rows = [dict(zip(cols, r)) for r in result.fetchall()]
                    return rows, None
                return "Query executed (no rows).", None
        except Exception as exc:
            return None, str(exc)

    @staticmethod
    def _clean_sql(sql: str) -> str:
        sql = sql.strip()
        sql = re.sub(r"^```(?:sql)?", "", sql).strip()
        sql = re.sub(r"```$", "", sql).strip()
        sql = sql.rstrip(";")
        return sql


    # ---------------- demo seeding ----------------
    def seed_demo(self) -> None:
        try:
            from sqlalchemy import update

            from .models import Product, SalesLine, SalesOrder

            factory = get_session_factory()
            with factory() as db:
                if db.query(Product).count() > 0:
                    return
                prods = [
                    Product(name="Wireless Mouse", category="Electronics", price=29.99, stock=120),
                    Product(name="Mechanical Keyboard", category="Electronics", price=99.99, stock=45),
                    Product(name="USB-C Hub", category="Electronics", price=49.99, stock=80),
                    Product(name="Office Chair", category="Furniture", price=299.99, stock=15),
                    Product(name="Standing Desk", category="Furniture", price=459.99, stock=10),
                    Product(name="Notebook", category="Stationery", price=4.99, stock=500),
                ]
                db.add_all(prods)
                db.flush()
                products = {p.name: p for p in prods}

                orders = [
                    SalesOrder(customer_name="Acme Corp", order_date="2024-01-05", status="completed", total=359.97),
                    SalesOrder(customer_name="Globex", order_date="2024-01-12", status="completed", total=99.99),
                    SalesOrder(customer_name="Initech", order_date="2024-02-02", status="pending", total=459.99),
                    SalesOrder(customer_name="Acme Corp", order_date="2024-02-18", status="completed", total=49.99),
                    SalesOrder(customer_name="Umbrella", order_date="2024-03-01", status="shipped", total=29.99),
                ]
                db.add_all(orders)
                db.flush()
                lines = [
                    SalesLine(order_id=orders[0].id, product_id=products["Wireless Mouse"].id, quantity=2, unit_price=29.99, line_total=59.98),
                    SalesLine(order_id=orders[1].id, product_id=products["Mechanical Keyboard"].id, quantity=1, unit_price=99.99, line_total=99.99),
                    SalesLine(order_id=orders[2].id, product_id=products["Standing Desk"].id, quantity=1, unit_price=459.99, line_total=459.99),
                    SalesLine(order_id=orders[3].id, product_id=products["USB-C Hub"].id, quantity=1, unit_price=49.99, line_total=49.99),
                    SalesLine(order_id=orders[4].id, product_id=products["Wireless Mouse"].id, quantity=1, unit_price=29.99, line_total=29.99),
                ]
                db.add_all(lines)
                db.commit()
                logger.info("seeded_demo_data", orders=len(orders), products=len(prods))
        except Exception as exc:  # pragma: no cover
            logger.error("seed_demo_failed", error=str(exc))

            return "\n".join(lines)
