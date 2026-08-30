package solution

import (
	"fmt"
	"testing"
)

func sameCook(got CookResult, vowels map[string]int, squeezes int, nums []int) bool {
	if got.Squeezes != squeezes {
		return false
	}
	if len(got.Vowels) != len(vowels) {
		return false
	}
	for k, v := range vowels {
		if got.Vowels[k] != v {
			return false
		}
	}
	if len(got.Nums) != len(nums) {
		return false
	}
	for i := range nums {
		if got.Nums[i] != nums[i] {
			return false
		}
	}
	return true
}

func hitCook(s string, vowels map[string]int, squeezes int, nums []int) (n int) {
	defer func() {
		if recover() != nil {
			n = 0
		}
	}()
	if sameCook(CookText(s), vowels, squeezes, nums) {
		return 1
	}
	return 0
}

func TestCookText(t *testing.T) {
	n := 0
	n += hitCook("", map[string]int{}, 0, nil)
	n += hitCook("book", map[string]int{"o": 2}, 1, nil)
	n += hitCook("a12b3", map[string]int{"a": 1}, 0, []int{12, 3})
	n += hitCook("AAE", map[string]int{"a": 2, "e": 1}, 1, nil)
	n += hitCook("x7y", map[string]int{}, 0, []int{7})
	fmt.Printf("POINTS %d/5\n", n)
}
