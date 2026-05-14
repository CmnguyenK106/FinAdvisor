package main

/*
Purpose: Holds runtime configuration and environment helpers for the gateway.
*/

import (
	"os"
	"strconv"
)

// config holds runtime configuration for the gateway.
type config struct {
	port     string
	agentURL string

	fireantBaseURL  string
	fireantToken    string
	fireantMinDelay int
	fireantCacheTTL int
}

// loadConfig reads environment variables for gateway configuration.
func loadConfig() config {
	token := os.Getenv("FIREANT_TOKEN")
	if token == "" {
		token = os.Getenv("FIREANT_API_KEY")
	}

	return config{
		port:     envOrDefault("PORT", "8081"),
		agentURL: os.Getenv("AGENT_URL"),

		fireantBaseURL:  envOrDefault("FIREANT_BASE_URL", "https://api.fireant.vn"),
		fireantToken:    token,
		fireantMinDelay: envOrDefaultInt("FIREANT_MIN_INTERVAL_MS", 300),
		fireantCacheTTL: envOrDefaultInt("FIREANT_CACHE_TTL_SEC", 300),
	}
}

func envOrDefaultInt(key string, fallback int) int {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}

	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return parsed
}

// envOrDefault returns an environment variable or a fallback value.
func envOrDefault(key, fallback string) string {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	return value
}
