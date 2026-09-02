package solution

import (
    "fmt"
    "reflect"
    "testing"
)
func boolInt(x bool) int { if x { return 1 }; return 0 }
func hitOrder(events [][2]string, want map[string]interface{}) int { defer func(){_ = recover()}(); return boolInt(reflect.DeepEqual(OrderEvents(events),want)) }
func TestOrderEvents(t *testing.T) {
 n:=0
 n+=hitOrder(nil,map[string]interface{}{"state":"CREATED","applied":[]string{},"rejected":[]string{}})
 n+=hitOrder([][2]string{{"p","PAY"},{"s","SHIP"},{"d","DELIVER"}},map[string]interface{}{"state":"DELIVERED","applied":[]string{"p","s","d"},"rejected":[]string{}})
 n+=hitOrder([][2]string{{"c","CANCEL"},{"p","PAY"}},map[string]interface{}{"state":"CANCELLED","applied":[]string{"c"},"rejected":[]string{"p"}})
 n+=hitOrder([][2]string{{"p","PAY"},{"p","PAY"}},map[string]interface{}{"state":"PAID","applied":[]string{"p"},"rejected":[]string{}})
 n+=hitOrder([][2]string{{"s","SHIP"},{"p","PAY"},{"r","REFUND"}},map[string]interface{}{"state":"REFUNDED","applied":[]string{"p","r"},"rejected":[]string{"s"}})
 n+=hitOrder([][2]string{{"p","PAY"},{"r","REFUND"},{"s","SHIP"}},map[string]interface{}{"state":"REFUNDED","applied":[]string{"p","r"},"rejected":[]string{"s"}})
 n+=hitOrder([][2]string{{"p","PAY"},{"s","SHIP"},{"r","REFUND"},{"d","DELIVER"}},map[string]interface{}{"state":"REFUNDED","applied":[]string{"p","s","r"},"rejected":[]string{"d"}})
 fmt.Printf("POINTS %d/7\n",n)
}
