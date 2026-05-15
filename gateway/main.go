package main

/*
Purpose: Bootstraps the API gateway by loading configuration and starting the HTTP server.
*/

import (
	"context"
	"log"

	"chatbot/memory"

	"github.com/joho/godotenv"
)

func main() {
	_ = godotenv.Load()
	_ = godotenv.Load("../.env")
	cfg := loadConfig()
	memCfg := memory.LoadConfig()
	ctx := context.Background()
	cache := buildCache(memCfg)
	storage := buildStorage(ctx, memCfg)
	srv := newServer(cfg, cache, storage)

	log.Printf("gateway listening on :%s", cfg.port)
	if err := srv.listenAndServe(); err != nil {
		log.Fatal(err)
	}
}
