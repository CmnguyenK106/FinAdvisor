package main

/*
Purpose: Defines a data gateway client for FireAnt and NewsData providers.
*/

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"chatbot/memory"
)

var (
	errFireAntNotConfigured  = errors.New("fireant not configured")
	errNewsDataNotConfigured = errors.New("newsdata not configured")
)

type dataGateway struct {
	fireantBaseURL  string
	fireantToken    string
	fireantMinDelay time.Duration
	fireantCacheTTL time.Duration
	newsDataBaseURL string
	newsDataAPIKey  string
	client          *http.Client
	cache           memory.Cache
	mu              sync.Mutex
	lastFireantCall time.Time
}

func newDataGateway(cfg config, cache memory.Cache) *dataGateway {
	minDelay := time.Duration(cfg.fireantMinDelay) * time.Millisecond
	if minDelay < 0 {
		minDelay = 0
	}

	cacheTTL := time.Duration(cfg.fireantCacheTTL) * time.Second
	if cacheTTL < 0 {
		cacheTTL = 0
	}

	return &dataGateway{
		fireantBaseURL:  cfg.fireantBaseURL,
		fireantToken:    cfg.fireantToken,
		fireantMinDelay: minDelay,
		fireantCacheTTL: cacheTTL,
		newsDataBaseURL: cfg.newsDataBaseURL,
		newsDataAPIKey:  cfg.newsDataAPIKey,
		client: &http.Client{
			Timeout: 20 * time.Second,
		},
		cache: cache,
	}
}

func (g *dataGateway) priceHistory(ctx context.Context, symbol, startDate, endDate string, limit int) (dataEnvelope, error) {
	path := fmt.Sprintf("/symbols/%s/historical-quotes", symbol)
	query := url.Values{}
	query.Set("startDate", startDate)
	query.Set("endDate", endDate)
	if limit > 0 {
		query.Set("limit", fmt.Sprintf("%d", limit))
	}

	var quotes []fireantQuote
	if err := g.fireantGet(ctx, path, query, &quotes); err != nil {
		return dataEnvelope{}, err
	}

	normalized := normalizeQuotes(quotes)
	return dataEnvelope{
		Source:      "fireant",
		RetrievedAt: time.Now().UTC(),
		Data: map[string]interface{}{
			"symbol": symbol,
			"start":  startDate,
			"end":    endDate,
			"quotes": normalized,
		},
	}, nil
}

func (g *dataGateway) fundamental(ctx context.Context, symbol string) (dataEnvelope, error) {
	path := fmt.Sprintf("/symbols/%s/fundamental", symbol)
	var raw fireantFundamental
	if err := g.fireantGet(ctx, path, nil, &raw); err != nil {
		return dataEnvelope{}, err
	}

	data := map[string]interface{}{
		"symbol":            raw.Symbol,
		"market_cap":        raw.MarketCap,
		"pe_multiple":       raw.PriceToEarning,
		"pb_multiple":       raw.PriceToBook,
		"dividend_yield":    raw.DividendYield,
		"eps":               raw.Eps,
		"roe":               raw.Roe,
		"roa":               raw.Roa,
		"net_profit_margin": raw.NetProfitMargin,
	}

	return dataEnvelope{
		Source:      "fireant",
		RetrievedAt: time.Now().UTC(),
		Data:        data,
	}, nil
}

func (g *dataGateway) financialsByPeriod(ctx context.Context, symbol string, year, quarter int) (dataEnvelope, error) {
	path := fmt.Sprintf("/symbols/%s/financial-data-by-period", symbol)
	query := url.Values{}
	query.Set("year", fmt.Sprintf("%d", year))
	query.Set("quarter", fmt.Sprintf("%d", quarter))

	var raw fireantFinancialByPeriod
	if err := g.fireantGet(ctx, path, query, &raw); err != nil {
		return dataEnvelope{}, err
	}

	return dataEnvelope{
		Source:      "fireant",
		RetrievedAt: time.Now().UTC(),
		Data: map[string]interface{}{
			"symbol":           raw.Symbol,
			"year":             raw.Year,
			"quarter":          raw.Quarter,
			"company_type":     raw.CompanyType,
			"icb_code":         raw.ICBCode,
			"icb_name":         raw.ICBName,
			"financial_values": raw.FinancialValues,
		},
	}, nil
}

func (g *dataGateway) financialReports(ctx context.Context, symbol string, reportType, year, quarter, limit int) (dataEnvelope, error) {
	path := fmt.Sprintf("/symbols/%s/full-financial-reports", symbol)
	query := url.Values{}
	query.Set("type", fmt.Sprintf("%d", reportType))
	query.Set("year", fmt.Sprintf("%d", year))
	query.Set("quarter", fmt.Sprintf("%d", quarter))
	if limit > 0 {
		query.Set("limit", fmt.Sprintf("%d", limit))
	}

	var raw []fireantReportItem
	if err := g.fireantGet(ctx, path, query, &raw); err != nil {
		return dataEnvelope{}, err
	}

	trimmed := trimReportItems(raw)
	return dataEnvelope{
		Source:      "fireant",
		RetrievedAt: time.Now().UTC(),
		Data: map[string]interface{}{
			"symbol":  symbol,
			"type":    reportType,
			"year":    year,
			"quarter": quarter,
			"reports": trimmed,
		},
	}, nil
}

func (g *dataGateway) estimatedPrice(ctx context.Context, symbol string) (dataEnvelope, error) {
	path := fmt.Sprintf("/symbols/%s/estimated-price", symbol)
	var raw map[string]interface{}
	if err := g.fireantGet(ctx, path, nil, &raw); err != nil {
		return dataEnvelope{}, err
	}

	return dataEnvelope{
		Source:      "fireant",
		RetrievedAt: time.Now().UTC(),
		Data:        raw,
	}, nil
}

func (g *dataGateway) posts(ctx context.Context, symbol string, postType, offset, limit int) (dataEnvelope, error) {
	path := fmt.Sprintf("/symbols/%s/posts", symbol)
	query := url.Values{}
	query.Set("type", fmt.Sprintf("%d", postType))
	query.Set("offset", fmt.Sprintf("%d", offset))
	if limit > 0 {
		query.Set("limit", fmt.Sprintf("%d", limit))
	}

	var raw []fireantPost
	if err := g.fireantGet(ctx, path, query, &raw); err != nil {
		return dataEnvelope{}, err
	}

	return dataEnvelope{
		Source:      "fireant",
		RetrievedAt: time.Now().UTC(),
		Data: map[string]interface{}{
			"symbol": symbol,
			"posts":  normalizePosts(raw),
		},
	}, nil
}

func (g *dataGateway) news(ctx context.Context, query, from, to string) (dataEnvelope, error) {
	if g.newsDataBaseURL == "" {
		return dataEnvelope{}, errNewsDataNotConfigured
	}

	path := "/api/1/news"
	queryParams := url.Values{}
	queryParams.Set("query", query)
	if from != "" {
		queryParams.Set("from", from)
	}
	if to != "" {
		queryParams.Set("to", to)
	}

	var raw map[string]interface{}
	if err := g.newsDataGet(ctx, path, queryParams, &raw); err != nil {
		return dataEnvelope{}, err
	}

	return dataEnvelope{
		Source:      "newsdata",
		RetrievedAt: time.Now().UTC(),
		Data:        raw,
	}, nil
}

func (g *dataGateway) fireantGet(ctx context.Context, path string, query url.Values, out interface{}) error {
	if g.fireantBaseURL == "" || g.fireantToken == "" {
		return errFireAntNotConfigured
	}
	if query == nil {
		query = url.Values{}
	}

	cacheKey := g.cacheKey(path, query)
	if g.cache != nil && g.fireantCacheTTL > 0 {
		if cached, ok, _ := g.cache.Get(ctx, cacheKey); ok {
			if err := json.Unmarshal([]byte(cached), out); err == nil {
				return nil
			}
		}
	}

	g.throttleFireant()

	requestURL := g.buildURL(g.fireantBaseURL, path, query)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, requestURL, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+g.fireantToken)

	resp, err := g.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("fireant api error: %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}

	if err := json.Unmarshal(body, out); err != nil {
		return err
	}

	if g.cache != nil && g.fireantCacheTTL > 0 {
		_ = g.cache.Set(ctx, cacheKey, string(body), g.fireantCacheTTL)
	}

	return nil
}

func (g *dataGateway) newsDataGet(ctx context.Context, path string, query url.Values, out interface{}) error {
	if g.newsDataBaseURL == "" || g.newsDataAPIKey == "" {
		return errNewsDataNotConfigured
	}
	if query == nil {
		query = url.Values{}
	}
	query.Set("apikey", g.newsDataAPIKey)

	requestURL := g.buildURL(g.newsDataBaseURL, path, query)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, requestURL, nil)
	if err != nil {
		return err
	}

	resp, err := g.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("newsdata api error: %d", resp.StatusCode)
	}

	return json.NewDecoder(resp.Body).Decode(out)
}

func (g *dataGateway) buildURL(baseURL, path string, query url.Values) string {
	base := strings.TrimRight(baseURL, "/")
	full := base + path
	if query.Encode() != "" {
		full += "?" + query.Encode()
	}
	return full
}

func (g *dataGateway) cacheKey(path string, query url.Values) string {
	encoded := query.Encode()
	if encoded == "" {
		return "fireant:" + path
	}
	return "fireant:" + path + "?" + encoded
}

func (g *dataGateway) throttleFireant() {
	if g.fireantMinDelay <= 0 {
		return
	}

	g.mu.Lock()
	defer g.mu.Unlock()
	if !g.lastFireantCall.IsZero() {
		elapsed := time.Since(g.lastFireantCall)
		if elapsed < g.fireantMinDelay {
			time.Sleep(g.fireantMinDelay - elapsed)
		}
	}
	g.lastFireantCall = time.Now()
}

type fireantFundamental struct {
	Symbol          string  `json:"symbol"`
	MarketCap       float64 `json:"marketCap"`
	PriceToEarning  float64 `json:"priceToEarning"`
	PriceToBook     float64 `json:"priceToBook"`
	DividendYield   float64 `json:"dividendYield"`
	Eps             float64 `json:"eps"`
	Roe             float64 `json:"roe"`
	Roa             float64 `json:"roa"`
	NetProfitMargin float64 `json:"netProfitMargin"`
}

type fireantFinancialByPeriod struct {
	Symbol          string             `json:"symbol"`
	Year            int                `json:"year"`
	Quarter         int                `json:"quarter"`
	CompanyType     string             `json:"companyType"`
	ICBCode         string             `json:"icbCode"`
	ICBName         string             `json:"icbName"`
	FinancialValues map[string]float64 `json:"financialValues"`
}

type fireantReportValue struct {
	Period  string  `json:"period"`
	Year    int     `json:"year"`
	Quarter int     `json:"quarter"`
	Value   float64 `json:"value"`
}

type fireantReportItem struct {
	Name   string               `json:"name"`
	Field  string               `json:"field"`
	Values []fireantReportValue `json:"values"`
}

type fireantPostSource struct {
	Name string `json:"name"`
	URL  string `json:"url"`
}

type fireantPost struct {
	PostID      int               `json:"postID"`
	Title       string            `json:"title"`
	Description string            `json:"description"`
	Summary     string            `json:"summary"`
	Content     string            `json:"content"`
	Date        string            `json:"date"`
	Sentiment   int               `json:"sentiment"`
	IsExpert    bool              `json:"isExpertIdea"`
	TotalLikes  int               `json:"totalLikes"`
	Source      fireantPostSource `json:"postSource"`
}

type fireantQuote struct {
	Date                string  `json:"date"`
	Symbol              string  `json:"symbol"`
	PriceHigh           float64 `json:"priceHigh"`
	PriceLow            float64 `json:"priceLow"`
	PriceOpen           float64 `json:"priceOpen"`
	PriceClose          float64 `json:"priceClose"`
	TotalVolume         float64 `json:"totalVolume"`
	BuyForeignValue     float64 `json:"buyForeignValue"`
	SellForeignValue    float64 `json:"sellForeignValue"`
	PropTradingNetValue float64 `json:"propTradingNetValue"`
}

func normalizeQuotes(quotes []fireantQuote) []map[string]interface{} {
	normalized := make([]map[string]interface{}, 0, len(quotes))
	for _, quote := range quotes {
		date := parseFireantDate(quote.Date)
		normalized = append(normalized, map[string]interface{}{
			"date":                   date,
			"open":                   quote.PriceOpen,
			"high":                   quote.PriceHigh,
			"low":                    quote.PriceLow,
			"close":                  quote.PriceClose,
			"total_volume":           quote.TotalVolume,
			"buy_foreign_value":      quote.BuyForeignValue,
			"sell_foreign_value":     quote.SellForeignValue,
			"prop_trading_net_value": quote.PropTradingNetValue,
		})
	}
	return normalized
}

func trimReportItems(items []fireantReportItem) []map[string]interface{} {
	trimmed := make([]map[string]interface{}, 0, len(items))
	for _, item := range items {
		values := make([]map[string]interface{}, 0, len(item.Values))
		for _, val := range item.Values {
			values = append(values, map[string]interface{}{
				"period":  val.Period,
				"year":    val.Year,
				"quarter": val.Quarter,
				"value":   val.Value,
			})
		}
		trimmed = append(trimmed, map[string]interface{}{
			"name":   item.Name,
			"field":  item.Field,
			"values": values,
		})
	}
	return trimmed
}

func normalizePosts(posts []fireantPost) []map[string]interface{} {
	normalized := make([]map[string]interface{}, 0, len(posts))
	for _, post := range posts {
		normalized = append(normalized, map[string]interface{}{
			"post_id":     post.PostID,
			"title":       post.Title,
			"summary":     post.Summary,
			"date":        post.Date,
			"sentiment":   post.Sentiment,
			"is_expert":   post.IsExpert,
			"total_likes": post.TotalLikes,
			"source": map[string]interface{}{
				"name": post.Source.Name,
				"url":  post.Source.URL,
			},
		})
	}
	return normalized
}

func parseFireantDate(value string) string {
	if value == "" {
		return ""
	}
	parsed, err := time.Parse("2006-01-02T15:04:05", value)
	if err != nil {
		return value
	}
	return parsed.UTC().Format(time.RFC3339)
}
