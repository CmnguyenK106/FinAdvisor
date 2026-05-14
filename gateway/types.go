package main

/*
Purpose: Defines shared request and response types for the gateway API.
*/

// agentRunRequest represents the payload from the web client.
type agentRunRequest struct {
	Query     string `json:"query"`
	UserID    string `json:"user_id,omitempty"`
	Asset     string `json:"asset,omitempty"`
	Locale    string `json:"locale,omitempty"`
	SessionID string `json:"session_id,omitempty"`
}

// agentRunResponse is returned when a run is accepted.
type agentRunResponse struct {
	RunID  string `json:"run_id"`
	Status string `json:"status"`
}

// agentStatusResponse reports the current state of a run.
type agentStatusResponse struct {
	RunID  string `json:"run_id"`
	Status string `json:"status"`
}

// agentResultResponse contains the final response payload.
type agentResultResponse struct {
	RunID    string   `json:"run_id"`
	Status   string   `json:"status"`
	Answer   string   `json:"answer,omitempty"`
	Sources  []string `json:"sources,omitempty"`
	Warnings []string `json:"warnings,omitempty"`
}
