package main

/*
Purpose: Wires the HTTP server, routes, and listener configuration.
*/

import (
	"net/http"
	"time"

	"chatbot/memory"
)

type server struct {
	cfg        config
	cache      memory.Cache
	store      memory.Storage
	data       *dataGateway
	mux        *http.ServeMux
	// httpClient is shared across all outbound calls to the agent service.
	// Creating a client per-request bypasses connection pooling.
	httpClient *http.Client
}

func newServer(cfg config, cache memory.Cache, store memory.Storage) *server {
	data := newDataGateway(cfg, cache)
	s := &server{
		cfg:   cfg,
		cache: cache,
		store: store,
		data:  data,
		mux:   http.NewServeMux(),
		httpClient: &http.Client{
			Timeout: 90 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        20,
				MaxIdleConnsPerHost: 20,
				IdleConnTimeout:     90 * time.Second,
			},
		},
	}
	s.registerRoutes()
	return s
}

func (s *server) registerRoutes() {
	// Simple health probe for container/platform checks.
	s.mux.HandleFunc("/health", s.handleHealth)

	// Starts a new agent run and returns a run ID.
	s.mux.HandleFunc("/api/agent/run", s.handleAgentRun)

	// Returns the status for a given run ID.
	s.mux.HandleFunc("/api/agent/status/", s.handleAgentStatus)

	// Returns the final result for a given run ID.
	s.mux.HandleFunc("/api/agent/result/", s.handleAgentResult)

	// Streaming (SSE) endpoint — tokens arrive in real time.
	s.mux.HandleFunc("/api/agent/stream", s.handleAgentStream)

	// Data gateway endpoints (finance).
	s.mux.HandleFunc("/data/price", s.handleDataPrice)
	s.mux.HandleFunc("/data/fundamental", s.handleDataFundamental)
	s.mux.HandleFunc("/data/financials", s.handleDataFinancials)
	s.mux.HandleFunc("/data/reports", s.handleDataReports)
	s.mux.HandleFunc("/data/ratios", s.handleDataRatios)
	s.mux.HandleFunc("/data/estimated-price", s.handleDataEstimatedPrice)
	s.mux.HandleFunc("/data/posts", s.handleDataPosts)
}

func (s *server) listenAndServe() error {
	// CORS is configured via ALLOWED_ORIGINS (comma-separated).
	return http.ListenAndServe(":"+s.cfg.port, withCORS(s.mux))
}
