package memory

/*
Purpose: Configuration helpers for cache and storage backends.
*/

import "os"

// Config captures connection settings for external backends.
type Config struct {
	RedisURL     string
	PostgresDSN  string
	CacheEnabled bool
}

// LoadConfig reads configuration from environment variables.
func LoadConfig() Config {
	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		redisURL = "redis://localhost:6379"
	}

	postgresDSN := os.Getenv("POSTGRES_DSN")
	if postgresDSN == "" {
		postgresDSN = "postgres://gateway:gatewaypass@localhost:5432/gatewaydb?sslmode=disable"
	}

	return Config{
		RedisURL:     redisURL,
		PostgresDSN:  postgresDSN,
		CacheEnabled: os.Getenv("CACHE_ENABLED") != "false",
	}
}
