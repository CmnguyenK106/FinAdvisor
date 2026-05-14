package memory

/*
Purpose: Storage access layer with an in-memory implementation.
*/

import (
	"context"
	"sync"
	"time"
)

// Storage defines persistence operations for agent runs.
type Storage interface {
	SaveAgentRun(ctx context.Context, run AgentRun) error
	GetAgentRun(ctx context.Context, runID string) (AgentRun, bool, error)
}

// InMemoryStorage is a lightweight storage layer for local development.
type InMemoryStorage struct {
	mu   sync.RWMutex
	runs map[string]AgentRun
}

// NewInMemoryStorage creates an empty storage instance.
func NewInMemoryStorage() *InMemoryStorage {
	return &InMemoryStorage{runs: make(map[string]AgentRun)}
}

// SaveAgentRun upserts a run record.
func (s *InMemoryStorage) SaveAgentRun(ctx context.Context, run AgentRun) error {
	now := time.Now().UTC()
	if run.CreatedAt.IsZero() {
		run.CreatedAt = now
	}
	run.UpdatedAt = now

	s.mu.Lock()
	s.runs[run.RunID] = run
	s.mu.Unlock()
	return nil
}

// GetAgentRun returns a run record by ID.
func (s *InMemoryStorage) GetAgentRun(ctx context.Context, runID string) (AgentRun, bool, error) {
	s.mu.RLock()
	run, ok := s.runs[runID]
	s.mu.RUnlock()
	return run, ok, nil
}
