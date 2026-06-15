// Sidecar LLM-прокси для JArbis — порт 17849.
// Go: быстрый HTTP с keep-alive и таймаутами для OpenRouter.
package main

import (
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"
)

var httpClient = &http.Client{Timeout: 120 * time.Second}

func env(key, def string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return def
}

func main() {
	port := env("JARBIS_LLM_PROXY_PORT", "17849")
	upstream := strings.TrimRight(env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"), "/")
	apiKey := os.Getenv("OPENAI_API_KEY")

	mux := http.NewServeMux()

	mux.HandleFunc("/ping", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok":      true,
			"backend": "go-llm-proxy",
			"port":    port,
		})
	})

	mux.HandleFunc("/v1/chat/completions", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		if apiKey == "" {
			w.Header().Set("Content-Type", "application/json; charset=utf-8")
			w.WriteHeader(http.StatusUnauthorized)
			_ = json.NewEncoder(w).Encode(map[string]any{
				"error": map[string]any{"message": "OPENAI_API_KEY not set"},
			})
			return
		}

		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		req, err := http.NewRequest(http.MethodPost, upstream+"/chat/completions", bytes.NewReader(body))
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", "Bearer "+apiKey)

		for _, h := range []string{"HTTP-Referer", "Referer", "X-Title"} {
			if v := r.Header.Get(h); v != "" {
				req.Header.Set(h, v)
			}
		}
		if req.Header.Get("Referer") == "" && req.Header.Get("HTTP-Referer") == "" {
			req.Header.Set("HTTP-Referer", "https://github.com/my-jarvis")
		}
		if req.Header.Get("X-Title") == "" {
			req.Header.Set("X-Title", "My-Jarvis")
		}

		resp, err := httpClient.Do(req)
		if err != nil {
			w.Header().Set("Content-Type", "application/json; charset=utf-8")
			w.WriteHeader(http.StatusBadGateway)
			_ = json.NewEncoder(w).Encode(map[string]any{
				"error": map[string]any{"message": err.Error()},
			})
			return
		}
		defer resp.Body.Close()

		for k, vals := range resp.Header {
			for _, v := range vals {
				w.Header().Add(k, v)
			}
		}
		w.WriteHeader(resp.StatusCode)
		_, _ = io.Copy(w, resp.Body)
	})

	addr := "127.0.0.1:" + port
	log.Printf("[go-llm-proxy] %s -> %s", addr, upstream)
	log.Fatal(http.ListenAndServe(addr, mux))
}
