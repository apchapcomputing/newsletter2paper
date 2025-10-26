package fetch

import (
	"context"
	"fmt"
	"sync"
	"time"

	"golang.org/x/sync/errgroup"
	art "newsletter2newspaper/internal/article"
	"newsletter2newspaper/internal/clean"
	"newsletter2newspaper/internal/images"
)

// ArticleResult holds the outcome of a single fetch attempt.
type ArticleResult struct {
	Article    *art.Article
	Err        error
	URL        string
	Index      int
	Elapsed    time.Duration
	CleanStats clean.Stats
}

// FetchArticlesConcurrent fetches multiple article URLs concurrently with a bounded level of parallelism.
// It returns a slice of successful Articles (in the order of the input URLs where possible) and a slice of errors.
// The function does NOT fail fast; all fetches attempt to run. Cancellation can still occur via the provided context.
func FetchArticlesConcurrent(ctx context.Context, urls []string, maxParallel int) ([]*art.Article, []error) {
	return FetchArticlesConcurrentWithImages(ctx, urls, maxParallel, nil)
}

// FetchArticlesConcurrentWithImages fetches multiple articles and optionally downloads images.
func FetchArticlesConcurrentWithImages(ctx context.Context, urls []string, maxParallel int, imageDownloader *images.Downloader) ([]*art.Article, []error) {
	if len(urls) == 0 {
		return nil, nil
	}
	if maxParallel <= 0 {
		maxParallel = 4
	}

	results := make([]*art.Article, len(urls))
	errs := make([]error, 0)
	sem := make(chan struct{}, maxParallel)
	var mu sync.Mutex

	g, ctx := errgroup.WithContext(ctx)

	for i, u := range urls {
		i, u := i, u
		g.Go(func() error {
			start := time.Now()
			sem <- struct{}{} // acquire
			defer func() { <-sem }()

			artc, _, err := FetchArticleWithImages(ctx, u, imageDownloader)

			mu.Lock()
			defer mu.Unlock()
			if err != nil {
				errs = append(errs, fmt.Errorf("%s: %w", u, err))
			} else {
				results[i] = artc
			}
			_ = time.Since(start) // (future: could log elapsed per URL)
			return nil // do not abort other goroutines
		})
	}

	_ = g.Wait() // collect all (ignoring aggregated error since we store per-URL errors)

	// Compact successful results preserving original relative order
	compacted := make([]*art.Article, 0, len(results))
	for _, r := range results {
		if r != nil {
			compacted = append(compacted, r)
		}
	}
	return compacted, errs
}
