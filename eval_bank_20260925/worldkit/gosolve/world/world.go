// 世界的数据结构。引擎和复核器都读它，但模拟规则各自实现。
package world

import "encoding/json"

type Order struct {
	Building string `json:"building"`
	Floor    int    `json:"floor"`
	Deadline int    `json:"deadline"`
	Ready    int    `json:"ready"`
}

type Outage struct {
	Spans   map[string][][2]int `json:"spans"`
	CheckAt string              `json:"check_at,omitempty"`
}

type Register struct {
	Minutes map[string]int `json:"minutes"`
}

type Closed struct {
	Spans map[string][][2]int `json:"spans"`
}

type Down struct {
	Rate int `json:"rate"`
}

type Congestion struct {
	From int `json:"from"`
	Mult int `json:"mult"`
}

type Carry struct {
	Max int `json:"max"`
}

type Cancel struct {
	IDs []string `json:"ids"`
}

type Flood struct {
	T        int    `json:"t"`
	Building string `json:"building"`
	Scope    string `json:"scope,omitempty"`
}

type Cold struct {
	Limit int `json:"limit"`
}

type Mutex struct {
	Force string `json:"force,omitempty"`
}

type Empty struct{}

type Modules struct {
	Outage     *Outage     `json:"outage,omitempty"`
	Register   *Register   `json:"register,omitempty"`
	Closed     *Closed     `json:"closed,omitempty"`
	Ready      *Empty      `json:"ready,omitempty"`
	Down       *Down       `json:"down,omitempty"`
	Congestion *Congestion `json:"congestion,omitempty"`
	Carry      *Carry      `json:"carry,omitempty"`
	ReturnW    *Empty      `json:"return_w,omitempty"`
	Cancel     *Cancel     `json:"cancel,omitempty"`
	Flood      *Flood      `json:"flood,omitempty"`
	Cold       *Cold       `json:"cold,omitempty"`
	Mutex      *Mutex      `json:"mutex,omitempty"`
}

type Data struct {
	Roads  map[string]int   `json:"roads"`
	Orders map[string]Order `json:"orders"`
	Role   string           `json:"role,omitempty"`
}

type Question struct {
	Name   string `json:"name"`
	Metric string `json:"metric"`
	Points int    `json:"points"`
	CF     string `json:"cf,omitempty"`
	Type   string `json:"type,omitempty"`
}

type Gates struct {
	MinDegree   *int `json:"min_degree,omitempty"`
	MinBoundary *int `json:"min_boundary,omitempty"`
}

type World struct {
	Family              string            `json:"family"`
	Data                Data              `json:"data"`
	Modules             Modules           `json:"modules"`
	Objective           []string          `json:"objective"`
	ObjectiveConditions map[string]string `json:"objective_conditions,omitempty"`
	Questions           []Question        `json:"questions"`
	Background          []string          `json:"background,omitempty"`
	Gates               Gates             `json:"gates,omitempty"`
	ActiveShock         string            `json:"active_shock,omitempty"`
}

func (w World) Clone() World {
	b, err := json.Marshal(w)
	if err != nil {
		panic(err)
	}
	var c World
	if err := json.Unmarshal(b, &c); err != nil {
		panic(err)
	}
	return c
}

func (w World) MainQuestions() []Question {
	var out []Question
	for _, q := range w.Questions {
		if q.CF == "" {
			out = append(out, q)
		}
	}
	return out
}

func Road(roads map[string]int, a, b string) int {
	if a == b {
		return 0
	}
	if v, ok := roads[a+"-"+b]; ok {
		return v
	}
	return roads[b+"-"+a]
}
