package main

/*
Purpose: Defines shared response envelopes for data gateway endpoints.
*/

import "time"

type dataEnvelope struct {
	Source      string      `json:"source"`
	RetrievedAt time.Time   `json:"retrieved_at"`
	Data        interface{} `json:"data"`
	Warnings    []string    `json:"warnings,omitempty"`
}
