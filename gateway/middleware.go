package main

/*
Purpose: Supplies HTTP helpers, including JSON responses and CORS handling.
*/

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
)

// writeJSON writes a JSON payload with the supplied status code.
func writeJSON(w http.ResponseWriter, status int, payload interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

// withCORS applies a minimal CORS policy for browser clients.
func withCORS(next http.Handler) http.Handler {
	allowedOrigins := os.Getenv("ALLOWED_ORIGINS")
	origins := map[string]bool{}
	if allowedOrigins != "" {
		for _, origin := range strings.Split(allowedOrigins, ",") {
			origins[strings.TrimSpace(origin)] = true
		}
	}

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if origin != "" {
			if len(origins) == 0 || origins[origin] {
				w.Header().Set("Access-Control-Allow-Origin", origin)
				w.Header().Set("Vary", "Origin")
			}
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		}

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}
