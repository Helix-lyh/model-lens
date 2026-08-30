import { ordersForUserSql } from "./solution";

let n = 0;
try {
  const sql = ordersForUserSql(42).toLowerCase();
  n += Number(sql.includes("select"));
  n += Number(!sql.split("from")[0].includes("*"));
  n += Number(sql.includes("user_id"));
  n += Number(["42", "?", "%s", ":user", "{user"].some((tok) => sql.includes(tok)));
  n += Number(sql.includes("order by"));
  n += Number(sql.includes("created_at"));
  n += Number(sql.includes("limit"));
} catch {
  /* keep n */
}
console.log(`POINTS ${n}/7`);
