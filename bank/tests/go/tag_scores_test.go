package solution

import (
	"fmt"
	"testing"
)

func eqTagMap(got, want map[string]int) bool {
	if len(got) != len(want) {
		return false
	}
	for k, v := range want {
		if got[k] != v {
			return false
		}
	}
	return true
}

func hitTag(items []string, want map[string]int) (n int) {
	defer func() {
		if recover() != nil {
			n = 0
		}
	}()
	if eqTagMap(TagScores(items), want) {
		return 1
	}
	return 0
}

func TestTagScores(t *testing.T) {
	n := 0
	n += hitTag([]string{}, map[string]int{})
	n += hitTag([]string{"a:1", "b:2", "a:3"}, map[string]int{"a": 4, "b": 2})
	n += hitTag([]string{"a:-3", "a:5"}, map[string]int{"a": 2})
	n += hitTag([]string{"x", ":5", "a:one", "a:1:2"}, map[string]int{})
	n += hitTag([]string{"cpu:10", "bad", "cpu:-4", "mem:7", ":9"}, map[string]int{"cpu": 6, "mem": 7})
	n += hitTag([]string{"a:+5", "a: 1", "a:1_000", "ok:-2"}, map[string]int{"ok": -2})
	fmt.Printf("POINTS %d/6\n", n)
}
