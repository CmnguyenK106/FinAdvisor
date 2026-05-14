package main

/*
Purpose: Builds cache and storage backends for the gateway.
*/

import (
	"context"
	"log"
	"time"

	"chatbot/memory"
)

type noopCache struct{}

func (n noopCache) Get(ctx context.Context, key string) (string, bool, error) {
	return "", false, nil
}

func (n noopCache) Set(ctx context.Context, key, value string, ttl time.Duration) error {
	return nil
}

func (n noopCache) Delete(ctx context.Context, key string) error {
	return nil
}

func buildCache(cfg memory.Config) memory.Cache {
	if !cfg.CacheEnabled {
		return noopCache{}
	}

	if cfg.RedisURL != "" {
		cache, err := memory.NewRedisCache(cfg.RedisURL)
		if err == nil {
			return cache
		}
		log.Printf("redis cache unavailable: %v; falling back to in-memory", err)
	}

	return memory.NewInMemoryCache()
}

func buildStorage(ctx context.Context, cfg memory.Config) memory.Storage {
	if cfg.PostgresDSN != "" {
		store, err := memory.NewPostgresStorage(ctx, cfg.PostgresDSN)
		if err == nil {
			if err := store.EnsureSchema(ctx); err != nil {
				log.Printf("postgres schema setup failed: %v", err)
			}
			return store
		}
		log.Printf("postgres storage unavailable: %v; falling back to in-memory", err)
	}

	return memory.NewInMemoryStorage()
}
