package solution

import (
    "fmt"
    "reflect"
    "testing"
)
func intList(v interface{}) ([]int,bool) { x,ok:=v.([]int); return x,ok }
func strMap(v interface{}) (map[string]string,bool) { x,ok:=v.(map[string]string); return x,ok }
func hitK(xs [][2]int, cap int, value, weight int, indices []int) int {
 defer func(){_ = recover()}()
 got:=BoundedKnapsack(xs,cap)
 v,vok:=got["value"].(int); w,wok:=got["weight"].(int); ix,iok:=intList(got["indices"])
 return boolInt(vok&&wok&&iok&&v==value&&w==weight&&reflect.DeepEqual(ix,indices))
}
func boolInt(x bool) int {if x{return 1};return 0}
func TestKnapsack(t *testing.T) {
 n:=0
 n+=hitK(nil,5,0,0,[]int{})
 n+=hitK([][2]int{{2,3}},1,0,0,[]int{})
 n+=hitK([][2]int{{4,7},{5,9},{6,10},{3,5}},10,17,10,[]int{0,2})
 n+=hitK([][2]int{{2,5},{2,5}},2,5,2,[]int{0})
 n+=hitK([][2]int{{1,-1},{2,4},{3,4}},3,4,2,[]int{1})
 n+=hitK([][2]int{{1,2},{2,4},{3,6}},3,6,3,[]int{0,1})
 fmt.Printf("POINTS %d/6\n",n)
}
