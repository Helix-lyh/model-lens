package solution

import (
	"fmt"
	"strings"
	"testing"
)

func TestOrdersForUserSQL(t *testing.T) {
	n := 0
	func() {
		defer func() { recover() }()
		sql := strings.ToLower(OrdersForUserSQL(42))
		n += btoi(strings.Contains(sql, "select"))
		head := sql
		if i := strings.Index(sql, "from"); i >= 0 {
			head = sql[:i]
		}
		n += btoi(!strings.Contains(head, "*"))
		n += btoi(strings.Contains(sql, "user_id"))
		n += btoi(strings.Contains(sql, "42") || strings.Contains(sql, "?") || strings.Contains(sql, "%s") || strings.Contains(sql, ":user") || strings.Contains(sql, "{user"))
		n += btoi(strings.Contains(sql, "order by"))
		n += btoi(strings.Contains(sql, "created_at"))
		n += btoi(strings.Contains(sql, "limit"))
	}()
	fmt.Printf("POINTS %d/7\n", n)
}

func btoi(ok bool) int {
	if ok {
		return 1
	}
	return 0
}
