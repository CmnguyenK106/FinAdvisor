package main

/*
Purpose: Implements HTTP handlers for data gateway endpoints (FireAnt + NewsData).
*/

import (
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"
)

func (s *server) handleDataPrice(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}

	symbol := strings.TrimSpace(r.URL.Query().Get("symbol"))
	if symbol == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "symbol is required"})
		return
	}

	startDate := strings.TrimSpace(r.URL.Query().Get("startDate"))
	endDate := strings.TrimSpace(r.URL.Query().Get("endDate"))
	rangeParam := strings.TrimSpace(r.URL.Query().Get("range"))
	if startDate == "" || endDate == "" {
		startDate, endDate = resolveDateRange(rangeParam)
	}

	limit := parseIntQuery(r, "limit", 200)

	res, err := s.data.priceHistory(r.Context(), symbol, startDate, endDate, limit)
	if err != nil {
		handleDataError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, res)
}

func (s *server) handleDataFinancials(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}

	symbol := strings.TrimSpace(r.URL.Query().Get("symbol"))
	if symbol == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "symbol is required"})
		return
	}

	year, quarter := resolveYearQuarter(r)
	res, err := s.data.financialsByPeriod(r.Context(), symbol, year, quarter)
	if err != nil {
		handleDataError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, res)
}

func (s *server) handleDataRatios(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}

	symbol := strings.TrimSpace(r.URL.Query().Get("symbol"))
	if symbol == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "symbol is required"})
		return
	}

	res, err := s.data.fundamental(r.Context(), symbol)
	if err != nil {
		handleDataError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, res)
}

func (s *server) handleDataNews(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}

	query := strings.TrimSpace(r.URL.Query().Get("query"))
	if query == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "query is required"})
		return
	}

	from := strings.TrimSpace(r.URL.Query().Get("from"))
	to := strings.TrimSpace(r.URL.Query().Get("to"))

	res, err := s.data.news(r.Context(), query, from, to)
	if err != nil {
		handleDataError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, res)
}

func (s *server) handleDataFundamental(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}

	symbol := strings.TrimSpace(r.URL.Query().Get("symbol"))
	if symbol == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "symbol is required"})
		return
	}

	res, err := s.data.fundamental(r.Context(), symbol)
	if err != nil {
		handleDataError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, res)
}

func (s *server) handleDataReports(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}

	symbol := strings.TrimSpace(r.URL.Query().Get("symbol"))
	if symbol == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "symbol is required"})
		return
	}

	reportType := parseIntQuery(r, "type", 2)
	year, quarter := resolveYearQuarter(r)
	limit := parseIntQuery(r, "limit", 5)

	res, err := s.data.financialReports(r.Context(), symbol, reportType, year, quarter, limit)
	if err != nil {
		handleDataError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, res)
}

func (s *server) handleDataEstimatedPrice(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}

	symbol := strings.TrimSpace(r.URL.Query().Get("symbol"))
	if symbol == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "symbol is required"})
		return
	}

	res, err := s.data.estimatedPrice(r.Context(), symbol)
	if err != nil {
		handleDataError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, res)
}

func (s *server) handleDataPosts(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}

	symbol := strings.TrimSpace(r.URL.Query().Get("symbol"))
	if symbol == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "symbol is required"})
		return
	}

	postType := parseIntQuery(r, "type", 1)
	offset := parseIntQuery(r, "offset", 0)
	limit := parseIntQuery(r, "limit", 20)

	res, err := s.data.posts(r.Context(), symbol, postType, offset, limit)
	if err != nil {
		handleDataError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, res)
}

func handleDataError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, errFireAntNotConfigured):
		writeJSON(w, http.StatusNotImplemented, map[string]string{"error": "fireant not configured"})
	case errors.Is(err, errNewsDataNotConfigured):
		writeJSON(w, http.StatusNotImplemented, map[string]string{"error": "newsdata not configured"})
	default:
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "data provider error"})
	}
}

func resolveDateRange(rangeParam string) (string, string) {
	if rangeParam == "" {
		rangeParam = "1y"
	}
	end := time.Now().UTC()
	start := end

	switch strings.ToLower(rangeParam) {
	case "1d":
		start = end.AddDate(0, 0, -1)
	case "1w":
		start = end.AddDate(0, 0, -7)
	case "1m":
		start = end.AddDate(0, -1, 0)
	case "6m":
		start = end.AddDate(0, -6, 0)
	case "3y":
		start = end.AddDate(-3, 0, 0)
	case "5y":
		start = end.AddDate(-5, 0, 0)
	default:
		start = end.AddDate(-1, 0, 0)
	}

	return start.Format(time.RFC3339), end.Format(time.RFC3339)
}

func resolveYearQuarter(r *http.Request) (int, int) {
	year := parseIntQuery(r, "year", time.Now().Year())
	quarter := parseIntQuery(r, "quarter", currentQuarter())
	return year, quarter
}

func currentQuarter() int {
	month := int(time.Now().Month())
	return (month-1)/3 + 1
}

func parseIntQuery(r *http.Request, key string, fallback int) int {
	value := strings.TrimSpace(r.URL.Query().Get(key))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return parsed
}
