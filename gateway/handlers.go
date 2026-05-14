package main

/*
Purpose: Implements HTTP handlers for gateway endpoints.
*/

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
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

	if strings.TrimSpace(s.cfg.agentURL) == "" {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "agent service not configured"})
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

	requestCopy := req
	go s.executeAgentRun(runID, requestCopy)

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

func (s *server) executeAgentRun(runID string, req agentRunRequest) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	resp, err := s.callAgentService(ctx, req)
	if err != nil {
		result := memory.AgentRun{
			RunID:    runID,
			Status:   "failed",
			Warnings: []string{err.Error()},
		}
		_ = s.store.SaveAgentRun(ctx, result)
		_ = s.cache.Set(ctx, cacheKeyStatus(runID), "failed", 5*time.Minute)
		return
	}

	result := memory.AgentRun{
		RunID:  runID,
		Status: "completed",
		Answer: resp.Answer,
	}
	_ = s.store.SaveAgentRun(ctx, result)
	_ = s.cache.Set(ctx, cacheKeyStatus(runID), "completed", 5*time.Minute)
}

func (s *server) callAgentService(ctx context.Context, req agentRunRequest) (agentServiceResponse, error) {
	endpoint, err := url.JoinPath(s.cfg.agentURL, "/agent/run")
	if err != nil {
		return agentServiceResponse{}, err
	}

	payload := agentServiceRequest{Query: req.Query, Locale: req.Locale}
	body, err := json.Marshal(payload)
	if err != nil {
		return agentServiceResponse{}, err
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return agentServiceResponse{}, err
	}
	httpReq.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 90 * time.Second}
	resp, err := client.Do(httpReq)
	if err != nil {
		return agentServiceResponse{}, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		snippet, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return agentServiceResponse{}, fmt.Errorf("agent service error: %d %s", resp.StatusCode, strings.TrimSpace(string(snippet)))
	}

	var decoded agentServiceResponse
	if err := json.NewDecoder(resp.Body).Decode(&decoded); err != nil {
		return agentServiceResponse{}, err
	}

	return decoded, nil
}

type agentServiceRequest struct {
	Query  string `json:"query"`
	Locale string `json:"locale,omitempty"`
}

type agentServiceResponse struct {
	Answer     string                   `json:"answer"`
	Confidence int                      `json:"confidence"`
	Valuations []map[string]interface{} `json:"valuations"`
}
