package solution

import (
    "fmt"
    "reflect"
    "testing"
)
func mapInt(v interface{}) (map[string]int,bool) {x,ok:=v.(map[string]int);return x,ok}
func hitMVCC(initial map[string]int, txns []map[string]interface{}, state map[string]int, statuses map[string]string) int {
 defer func(){_ = recover()}()
 got:=ApplyTransactions(initial,txns)
 gs,sok:=mapInt(got["state"]); st,tok:=got["statuses"].(map[string]string)
 return boolInt(sok&&tok&&reflect.DeepEqual(gs,state)&&reflect.DeepEqual(st,statuses))
}
func boolInt(x bool) int {if x{return 1};return 0}
func TestMVCC(t *testing.T) {
 n:=0
 n+=hitMVCC(map[string]int{},nil,map[string]int{},map[string]string{})
 n+=hitMVCC(map[string]int{"a":0},[]map[string]interface{}{{"id":"t1","begin":0,"writes":map[string]interface{}{"a":2},"commit":1}},map[string]int{"a":2},map[string]string{"t1":"COMMIT"})
 n+=hitMVCC(map[string]int{"a":0},[]map[string]interface{}{{"id":"t1","begin":0,"writes":map[string]interface{}{"a":2},"commit":2},{"id":"t2","begin":0,"writes":map[string]interface{}{"a":3},"commit":1}},map[string]int{"a":3},map[string]string{"t1":"ABORT","t2":"COMMIT"})
 n+=hitMVCC(map[string]int{"a":0},[]map[string]interface{}{{"id":"t1","begin":0,"writes":map[string]interface{}{"a":2},"commit":1},{"id":"t2","begin":0,"writes":map[string]interface{}{"a":3},"commit":2}},map[string]int{"a":2},map[string]string{"t1":"COMMIT","t2":"ABORT"})
 n+=hitMVCC(map[string]int{"a":0,"b":0},[]map[string]interface{}{{"id":"x","begin":0,"writes":map[string]interface{}{"a":1},"commit":1},{"id":"y","begin":0,"writes":map[string]interface{}{"b":2},"commit":2}},map[string]int{"a":1,"b":2},map[string]string{"x":"COMMIT","y":"COMMIT"})
 n+=hitMVCC(map[string]int{"a":1},[]map[string]interface{}{{"id":"late","begin":1,"writes":map[string]interface{}{"a":9},"commit":3},{"id":"early","begin":0,"writes":map[string]interface{}{"a":4},"commit":2}},map[string]int{"a":9},map[string]string{"late":"COMMIT","early":"COMMIT"})
 fmt.Printf("POINTS %d/6\n",n)
}
