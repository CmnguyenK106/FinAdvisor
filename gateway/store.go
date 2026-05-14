package main

/*
Purpose: Provides the in-memory run store used by the gateway stub.
*/

import (
	"sync"
	"time"
)

// runStore keeps minimal in-memory state for demo purposes.
// Replace this with persistent storage for production.
type runStore struct {
	mu      sync.Mutex
	status  map[string]string
	results map[string]agentResultResponse
}

// newRunStore initializes an in-memory run store.
func newRunStore() *runStore {
	return &runStore{
		status:  make(map[string]string),
		results: make(map[string]agentResultResponse),
	}
}

// createRun allocates a new run ID and marks it as queued.
func (s *runStore) createRun() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	id := time.Now().UTC().Format("20060102T150405.000000000Z")
	s.status[id] = "queued"
	return id
}

// setStatus updates the status for a run ID.
func (s *runStore) setStatus(id, status string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.status[id] = status
}

// getStatus retrieves the current status for a run ID.
func (s *runStore) getStatus(id string) (string, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	status, ok := s.status[id]
	return status, ok
}

// setResult stores the final result for a run ID.
func (s *runStore) setResult(result agentResultResponse) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.results[result.RunID] = result
}

// getResult returns the stored result for a run ID.
func (s *runStore) getResult(id string) (agentResultResponse, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	res, ok := s.results[id]
	return res, ok
}
