package solution

import (
    "fmt"
    "reflect"
    "testing"
)
func pairSlice(v interface{}) ([][2]int, bool) {
    x, ok := v.([][2]int); return x, ok
}
func hitMerge(xs [][2]int, budget int, okWant bool, ints [][2]int, reason string) int {
    defer func(){_ = recover()}()
    got := MergeBudget(xs,budget)
    ok, okType := got["ok"].(bool)
    gotIntervals, intType := pairSlice(got["intervals"])
    why, whyType := got["reason"].(string)
    return boolInt(okType && intType && whyType && ok==okWant && reflect.DeepEqual(gotIntervals,ints) && why==reason)
}
func boolInt(x bool) int { if x { return 1 }; return 0 }
func TestMergeBudget(t *testing.T) {
 n:=0
 n+=hitMerge(nil,0,true,[][2]int{},"empty")
 n+=hitMerge([][2]int{{1,3},{3,5}},5,true,[][2]int{{1,5}},"empty")
 n+=hitMerge([][2]int{{5,7},{1,2},{2,4}},7,true,[][2]int{{1,7}},"empty")
 n+=hitMerge([][2]int{{1,3},{10,10}},3,false,[][2]int{},"budget_exceeded")
 n+=hitMerge([][2]int{{3,2}},10,false,[][2]int{},"invalid")
 n+=hitMerge([][2]int{{0,0},{-2,-1}},3,true,[][2]int{{-2,0}},"empty")
 fmt.Printf("POINTS %d/6\n",n)
}
