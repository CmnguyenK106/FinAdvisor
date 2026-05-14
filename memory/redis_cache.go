package memory

/*
Purpose: Redis-backed cache implementation.
*/

import (
	"context"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
)

// RedisCache implements Cache using Redis as backend.
type RedisCache struct {
	client *redis.Client
}

// NewRedisCache creates a Redis cache from a URL or host:port.
func NewRedisCache(redisURL string) (*RedisCache, error) {
	var options *redis.Options
	var err error

	if strings.HasPrefix(redisURL, "redis://") || strings.HasPrefix(redisURL, "rediss://") {
		options, err = redis.ParseURL(redisURL)
		if err != nil {
			return nil, err
		}
	} else {
		options = &redis.Options{Addr: redisURL}
	}

	client := redis.NewClient(options)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := client.Ping(ctx).Err(); err != nil {
		_ = client.Close()
		return nil, err
	}

	return &RedisCache{client: client}, nil
}

// Get returns a cached value if present.
func (c *RedisCache) Get(ctx context.Context, key string) (string, bool, error) {
	value, err := c.client.Get(ctx, key).Result()
	if err == redis.Nil {
		return "", false, nil
	}
	if err != nil {
		return "", false, err
	}
	return value, true, nil
}

// Set stores a cached value with optional TTL.
func (c *RedisCache) Set(ctx context.Context, key, value string, ttl time.Duration) error {
	return c.client.Set(ctx, key, value, ttl).Err()
}

// Delete removes a cached item.
func (c *RedisCache) Delete(ctx context.Context, key string) error {
	return c.client.Del(ctx, key).Err()
}

// Close releases the Redis connection.
func (c *RedisCache) Close() error {
	return c.client.Close()
}
