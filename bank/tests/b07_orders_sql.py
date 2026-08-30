from solution import orders_for_user_sql

n = 0
try:
    sql = orders_for_user_sql(42).lower()
    n += int("select" in sql)
    n += int("*" not in sql.split("from")[0])
    n += int("user_id" in sql)
    n += int(any(tok in sql for tok in ("42", "?", "%s", ":user", "{user")))
    n += int("order by" in sql)
    n += int("created_at" in sql)
    n += int("limit" in sql)
except Exception as exc:
    print("MISS", type(exc).__name__)
print(f"POINTS {n}/7")
