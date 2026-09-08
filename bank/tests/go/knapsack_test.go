package solution

import (
    "fmt"
    "reflect"
    "testing"
)
func intList(v interface{}) ([]int,bool) {
 x,ok:=v.([]int)
 if !ok { return nil,false }
 if x==nil { x=[]int{} }
 return x,true
}
func strMap(v interface{}) (map[string]string,bool) { x,ok:=v.(map[string]string); return x,ok }
func hitK(xs [][2]int, cap int, value, weight int, indices []int) int {
 defer func(){_ = recover()}()
 got:=BoundedKnapsack(xs,cap)
 v,vok:=got["value"].(int); w,wok:=got["weight"].(int); ix,iok:=intList(got["indices"])
 return boolInt(vok&&wok&&iok&&v==value&&w==weight&&reflect.DeepEqual(ix,indices))
}
func boolInt(x bool) int {if x{return 1};return 0}
func lexK(a,b []int) bool {
 for i:=0;i<len(a)&&i<len(b);i++ {if a[i]!=b[i] {return a[i]<b[i]}}
 return len(a)<len(b)
}
func oracleK(xs [][2]int, cap int) (int,int,[]int) {
 bv,bw:=0,0; bi:=[]int{}
 for mask:=0;mask<(1<<len(xs));mask++ {
  v,w:=0,0; ix:=[]int{}
  for i,x:=range xs {if mask&(1<<i)!=0 {w+=x[0];v+=x[1];ix=append(ix,i)}}
  if w<=cap&&(v>bv||(v==bv&&lexK(ix,bi))) {bv,bw,bi=v,w,ix}
 }
 return bv,bw,bi
}
func TestKnapsack(t *testing.T) {
 n:=0
 n+=hitK(nil,5,0,0,[]int{})
 n+=hitK([][2]int{{2,3}},1,0,0,[]int{})
 n+=hitK([][2]int{{4,7},{5,9},{6,10},{3,5}},10,17,10,[]int{0,2})
 n+=hitK([][2]int{{2,5},{2,5}},2,5,2,[]int{0})
 n+=hitK([][2]int{{1,-1},{2,4},{3,4}},3,4,2,[]int{1})
 n+=hitK([][2]int{{1,2},{2,4},{3,6}},3,6,3,[]int{0,1})
 n+=hitK([][2]int{{5,10},{1,10}},5,10,5,[]int{0})
 for seed:=0; seed<12; seed++ {
  xs:=make([][2]int,5)
  for i:=range xs {xs[i]=[2]int{(seed*7+i*3)%6+1,(seed*11+i*5)%13-3}}
  cap:=(seed*5)%13
  value,weight,indices:=oracleK(xs,cap)
  n+=hitK(xs,cap,value,weight,indices)
 }
 fmt.Printf("POINTS %d/19\n",n)
}
