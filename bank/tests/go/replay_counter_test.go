package solution

import (
    "fmt"
    "testing"
)

func replaySlice(v interface{}) ([]string, bool) {
    switch x := v.(type) {
    case []string:
        return x, true
    case []interface{}:
        out := make([]string, len(x))
        for i, item := range x { s, ok := item.(string); if !ok { return nil, false }; out[i] = s }
        return out, true
    default:
        return nil, false
    }
}
func replayInt(v interface{}) (int, bool) { x, ok := v.(int); return x, ok }
func eqStrings(a, b []string) bool { if len(a)!=len(b){return false}; for i:=range a {if a[i]!=b[i]{return false}}; return true }
func hitReplay(log [][3]interface{}, balance int, accepted, rejected []string) int {
    defer func(){ _ = recover() }()
    got := ReplayCounter(log)
    b, bok := replayInt(got["balance"])
    a, aok := replaySlice(got["accepted"])
    r, rok := replaySlice(got["rejected"])
    return boolInt(bok && aok && rok && b == balance && eqStrings(a, accepted) && eqStrings(r, rejected))
}
func boolInt(x bool) int { if x { return 1 }; return 0 }
func TestReplayCounter(t *testing.T) {
    n:=0
    n+=hitReplay(nil,0,[]string{},[]string{})
    n+=hitReplay([][3]interface{}{{"a","credit",10},{"b","debit",3}},7,[]string{"a","b"},[]string{})
    n+=hitReplay([][3]interface{}{{"a","credit",5},{"a","credit",9}},5,[]string{"a"},[]string{"a"})
    n+=hitReplay([][3]interface{}{{"x","debit",1}},0,[]string{},[]string{"x"})
    n+=hitReplay([][3]interface{}{{"a","credit",10},{"b","debit",6},{"c","refund",4}},8,[]string{"a","b","c"},[]string{})
    n+=hitReplay([][3]interface{}{{"a","credit",2},{"c","refund",1},{"b","debit",1},{"c","refund",5}},1,[]string{"a","b"},[]string{"c","c"})
    n+=hitReplay([][3]interface{}{{"a","credit",1},{"b","debit",1},{"c","refund",2}},0,[]string{"a","b"},[]string{"c"})
    fmt.Printf("POINTS %d/7\n",n)
}
