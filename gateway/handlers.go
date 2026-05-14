package main

/*
Purpose: Implements HTTP handlers for gateway endpoints.
*/

import (
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"chatbot/memory"
)

func (s *server) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *server) handleAgentRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}

	var req agentRunRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid request"})
		return
	}
	if strings.TrimSpace(req.Query) == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "query is required"})
		return
	}

	runID := newRunID()
	if err := s.store.SaveAgentRun(r.Context(), memory.AgentRun{RunID: runID, Status: "running"}); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to start run"})
		return
	}
	_ = s.cache.Set(r.Context(), cacheKeyStatus(runID), "running", 5*time.Minute)

	// TODO: Replace this stub with a call to the agent service at s.cfg.agentURL.
	result := memory.AgentRun{
		RunID:  runID,
		Status: "completed",
		Answer: "gateway stub: agent response will be provided by the agent service",
		Warnings: []string{
			"agent service not wired yet",
		},
	}
	if err := s.store.SaveAgentRun(r.Context(), result); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to store result"})
		return
	}
	_ = s.cache.Set(r.Context(), cacheKeyStatus(runID), "completed", 5*time.Minute)

	writeJSON(w, http.StatusAccepted, agentRunResponse{RunID: runID, Status: "running"})
}

func (s *server) handleAgentStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}

	runID := strings.TrimPrefix(r.URL.Path, "/api/agent/status/")
	if runID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "run id required"})
		return
	}

	if status, ok, _ := s.cache.Get(r.Context(), cacheKeyStatus(runID)); ok {
		writeJSON(w, http.StatusOK, agentStatusResponse{RunID: runID, Status: status})
		return
	}

	run, ok, err := s.store.GetAgentRun(r.Context(), runID)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to load run"})
		return
	}
	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "run not found"})
		return
	}

	_ = s.cache.Set(r.Context(), cacheKeyStatus(runID), run.Status, 5*time.Minute)
	writeJSON(w, http.StatusOK, agentStatusResponse{RunID: runID, Status: run.Status})
}

func (s *server) handleAgentResult(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}

	runID := strings.TrimPrefix(r.URL.Path, "/api/agent/result/")
	if runID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "run id required"})
		return
	}

	run, ok, err := s.store.GetAgentRun(r.Context(), runID)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to load result"})
		return
	}
	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "result not found"})
		return
	}

	writeJSON(w, http.StatusOK, agentResultResponse{
		RunID:    run.RunID,
		Status:   run.Status,
		Answer:   run.Answer,
		Sources:  run.Sources,
		Warnings: run.Warnings,
	})
}

func newRunID() string {
	return time.Now().UTC().Format("20060102T150405.000000000Z")
}

func cacheKeyStatus(runID string) string {
	return "run_status:" + runID
}
