package main

import (
	"bufio"
	"encoding/json"
	"os"

	"worldkitsolve/gates"
)

func main() {
	in := bufio.NewScanner(os.Stdin)
	in.Buffer(make([]byte, 1<<20), 8<<20)
	out := bufio.NewWriter(os.Stdout)
	enc := json.NewEncoder(out)
	for in.Scan() {
		var req gates.Request
		if err := json.Unmarshal(in.Bytes(), &req); err != nil {
			_ = enc.Encode(map[string]any{"id": req.ID, "error": err.Error()})
			_ = out.Flush()
			continue
		}
		var rep map[string]any
		var err error
		if req.Op == "status" {
			rep, err = gates.Status(req)
		} else if req.Op == "trajectory" {
			rep, err = gates.Trajectory(req)
		} else {
			rep, err = gates.Run(req)
		}
		resp := map[string]any{"id": req.ID, "report": rep}
		if err != nil {
			resp["error"] = err.Error()
		}
		_ = enc.Encode(resp)
		_ = out.Flush()
	}
}
