package memory

/*
Purpose: Cache access layer with a simple in-memory implementation.
*/

import (
	"context"
	"sync"
	"time"
)

// Cache defines a minimal contract for read/write caching.
type Cache interface {
	Get(ctx context.Context, key string) (string, bool, error)
	Set(ctx context.Context, key, value string, ttl time.Duration) error
	Delete(ctx context.Context, key string) error
}

type cacheItem struct {
	value     string
	expiresAt time.Time
}

// InMemoryCache is a lightweight cache for local development.
type InMemoryCache struct {
	mu    sync.RWMutex
	items map[string]cacheItem
}

// NewInMemoryCache creates an empty cache instance.
func NewInMemoryCache() *InMemoryCache {
	return &InMemoryCache{
		items: make(map[string]cacheItem),
	}
}

// Get returns a cached value if present and not expired.
func (c *InMemoryCache) Get(ctx context.Context, key string) (string, bool, error) {
	c.mu.RLock()
	item, ok := c.items[key]
	c.mu.RUnlock()
	if !ok {
		return "", false, nil
	}

	if !item.expiresAt.IsZero() && time.Now().After(item.expiresAt) {
		_ = c.Delete(ctx, key)
		return "", false, nil
	}

	return item.value, true, nil
}

// Set stores a cached value with an optional TTL.
func (c *InMemoryCache) Set(ctx context.Context, key, value string, ttl time.Duration) error {
	item := cacheItem{value: value}
	if ttl > 0 {
		item.expiresAt = time.Now().Add(ttl)
	}

	c.mu.Lock()
	c.items[key] = item
	c.mu.Unlock()
	return nil
}

// Delete removes a cached item.
func (c *InMemoryCache) Delete(ctx context.Context, key string) error {
	c.mu.Lock()
	delete(c.items, key)
	c.mu.Unlock()
	return nil
}
