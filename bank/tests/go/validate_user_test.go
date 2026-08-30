package solution

import (
	"fmt"
	"testing"
)

func hasField(xs []string, w string) bool {
	for _, x := range xs {
		if x == w {
			return true
		}
	}
	return false
}

func TestValidateUser(t *testing.T) {
	n := 0
	func() {
		defer func() { recover() }()
		if len(ValidateUser(map[string]any{"name": "ann", "age": 20})) == 0 {
			n++
		}
	}()
	func() {
		defer func() { recover() }()
		if hasField(ValidateUser(map[string]any{"name": "", "age": 20}), "name") {
			n++
		}
	}()
	func() {
		defer func() { recover() }()
		if hasField(ValidateUser(map[string]any{"name": "ann", "age": 200}), "age") {
			n++
		}
	}()
	func() {
		defer func() { recover() }()
		if hasField(ValidateUser(map[string]any{"name": "ann"}), "age") {
			n++
		}
	}()
	func() {
		defer func() { recover() }()
		if hasField(ValidateUser(map[string]any{"age": 3}), "name") {
			n++
		}
	}()
	fmt.Printf("POINTS %d/5\n", n)
}
