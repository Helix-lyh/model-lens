package solution

import (
	"fmt"
	"testing"
)

func hitRender(tpl string, vars map[string]string, want string) (n int) {
	defer func() {
		if recover() != nil {
			n = 0
		}
	}()
	if Render(tpl, vars) == want {
		return 1
	}
	return 0
}

func TestRender(t *testing.T) {
	n := 0
	n += hitRender("hello", map[string]string{}, "hello")
	n += hitRender("hi {name}!", map[string]string{"name": "Tom"}, "hi Tom!")
	n += hitRender("{a}+{b}", map[string]string{"a": "1"}, "1+{b}")
	n += hitRender("{{name}}", map[string]string{"name": "X"}, "{name}")
	n += hitRender("{a b} { {}", map[string]string{}, "{a b} { {}")
	n += hitRender("{x}{{y}}{z}", map[string]string{"x": "1", "z": "2"}, "1{y}2")
	n += hitRender("{{{name}}}", map[string]string{"name": "Tom"}, "{Tom}")
	n += hitRender("{{y}}", map[string]string{"y": "Y"}, "{y}")
	fmt.Printf("POINTS %d/8\n", n)
}
