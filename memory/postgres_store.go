package memory

/*
Purpose: Postgres-backed storage implementation.
*/

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// PostgresStorage implements Storage using Postgres.
type PostgresStorage struct {
	pool *pgxpool.Pool
}

// NewPostgresStorage creates a Postgres storage instance.
func NewPostgresStorage(ctx context.Context, dsn string) (*PostgresStorage, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}

	return &PostgresStorage{pool: pool}, nil
}

// EnsureSchema creates the required tables if missing.
func (s *PostgresStorage) EnsureSchema(ctx context.Context) error {
	_, err := s.pool.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS agent_runs (
			run_id TEXT PRIMARY KEY,
			status TEXT NOT NULL,
			answer TEXT,
			confidence INT,
			valuations JSONB,
			sources JSONB,
			warnings JSONB,
			created_at TIMESTAMPTZ NOT NULL,
			updated_at TIMESTAMPTZ NOT NULL
		);
	`)
	if err != nil {
		return err
	}

	if _, err := s.pool.Exec(ctx, `ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS confidence INT`); err != nil {
		return err
	}
	if _, err := s.pool.Exec(ctx, `ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS valuations JSONB`); err != nil {
		return err
	}
	return nil
}

// SaveAgentRun upserts an agent run record.
func (s *PostgresStorage) SaveAgentRun(ctx context.Context, run AgentRun) error {
	if run.RunID == "" {
		return errors.New("run id is required")
	}

	now := time.Now().UTC()
	if run.CreatedAt.IsZero() {
		run.CreatedAt = now
	}
	run.UpdatedAt = now

	sourcesJSON, err := json.Marshal(run.Sources)
	if err != nil {
		return err
	}
	valuationsJSON, err := json.Marshal(run.Valuations)
	if err != nil {
		return err
	}
	warningsJSON, err := json.Marshal(run.Warnings)
	if err != nil {
		return err
	}

	_, err = s.pool.Exec(ctx, `
		INSERT INTO agent_runs (run_id, status, answer, confidence, valuations, sources, warnings, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		ON CONFLICT (run_id) DO UPDATE SET
			status = EXCLUDED.status,
			answer = EXCLUDED.answer,
			confidence = EXCLUDED.confidence,
			valuations = EXCLUDED.valuations,
			sources = EXCLUDED.sources,
			warnings = EXCLUDED.warnings,
			updated_at = EXCLUDED.updated_at;
	`, run.RunID, run.Status, run.Answer, run.Confidence, valuationsJSON, sourcesJSON, warningsJSON, run.CreatedAt, run.UpdatedAt)
	return err
}

// GetAgentRun fetches an agent run record by ID.
func (s *PostgresStorage) GetAgentRun(ctx context.Context, runID string) (AgentRun, bool, error) {
	var run AgentRun
	var sourcesJSON []byte
	var valuationsJSON []byte
	var warningsJSON []byte

	err := s.pool.QueryRow(ctx, `
		SELECT run_id, status, answer, COALESCE(confidence, 0), COALESCE(valuations, '[]'::jsonb), sources, warnings, created_at, updated_at
		FROM agent_runs
		WHERE run_id = $1;
	`, runID).Scan(&run.RunID, &run.Status, &run.Answer, &run.Confidence, &valuationsJSON, &sourcesJSON, &warningsJSON, &run.CreatedAt, &run.UpdatedAt)

	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return AgentRun{}, false, nil
		}
		return AgentRun{}, false, err
	}

	if len(sourcesJSON) > 0 {
		_ = json.Unmarshal(sourcesJSON, &run.Sources)
	}
	if len(valuationsJSON) > 0 {
		_ = json.Unmarshal(valuationsJSON, &run.Valuations)
	}
	if len(warningsJSON) > 0 {
		_ = json.Unmarshal(warningsJSON, &run.Warnings)
	}

	return run, true, nil
}

// Close releases the Postgres pool.
func (s *PostgresStorage) Close() {
	s.pool.Close()
}
