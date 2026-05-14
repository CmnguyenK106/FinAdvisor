# Memory Layer (Cache + Storage)

This folder provides cache and storage access layers for the gateway and agent services.

## Components
- `cache.go`: Cache interface + in-memory cache (dev default).
- `redis_cache.go`: Redis cache adapter.
- `storage.go`: Storage interface + in-memory storage (dev default).
- `postgres_store.go`: Postgres storage adapter.
- `models.go`: Shared data models (e.g., AgentRun).
- `config.go`: Backend configuration helpers.

## Environment Variables
- `REDIS_URL` (optional) - Redis URL or host:port.
- `POSTGRES_DSN` (optional) - Postgres connection string.
- `CACHE_ENABLED` (optional) - Set to `false` to disable cache entirely.

## Usage (Dev)
```go
cache := memory.NewInMemoryCache()
storage := memory.NewInMemoryStorage()
```

## Usage (Production)
```go
cfg := memory.LoadConfig()
cache := memory.NewRedisCache(cfg.RedisURL)
store, _ := memory.NewPostgresStorage(context.Background(), cfg.PostgresDSN)
```
