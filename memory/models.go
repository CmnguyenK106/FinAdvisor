package memory

/*
Purpose: Shared storage models for cache and persistence layers.
*/

import "time"

// AgentRun represents a stored agent execution.
type AgentRun struct {
	RunID     string
	Status    string
	Answer    string
	Sources   []string
	Warnings  []string
	CreatedAt time.Time
	UpdatedAt time.Time
}
