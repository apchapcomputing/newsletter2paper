package fetch

import (
	"context"
	"fmt"
	"time"

	"golang.org/x/sync/errgroup"
	art "pdf-maker/internal/article"
	"pdf-maker/internal/clean"
	"pdf-maker/internal/media"
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
// Successful articles are returned compacted (failures removed); use FetchArticlesAligned when
// each result must be matched back to its input URL.
func FetchArticlesConcurrentWithImages(ctx context.Context, urls []string, maxParallel int, imageDownloader *media.Downloader) ([]*art.Article, []error) {
	results, errs := FetchArticlesAligned(ctx, urls, maxParallel, imageDownloader)
	if results == nil {
		return nil, nil
	}

	compacted := make([]*art.Article, 0, len(results))
	for _, r := range results {
		if r != nil {
			compacted = append(compacted, r)
		}
	}
	failures := make([]error, 0)
	for _, e := range errs {
		if e != nil {
			failures = append(failures, e)
		}
	}
	return compacted, failures
}

// FetchArticlesAligned fetches every URL with bounded parallelism and returns two slices the
// same length as urls: results[i] is the article for urls[i] (nil if it failed) and errs[i] is
// the corresponding error (nil if it succeeded). It never fails fast.
func FetchArticlesAligned(ctx context.Context, urls []string, maxParallel int, imageDownloader *media.Downloader) ([]*art.Article, []error) {
	if len(urls) == 0 {
		return nil, nil
	}
	if maxParallel <= 0 {
		maxParallel = 4
	}

	results := make([]*art.Article, len(urls))
	errs := make([]error, len(urls))
	sem := make(chan struct{}, maxParallel)

	g, ctx := errgroup.WithContext(ctx)
	for i, u := range urls {
		i, u := i, u
		g.Go(func() error {
			sem <- struct{}{} // acquire
			defer func() { <-sem }()

			artc, _, err := FetchArticleWithImages(ctx, u, imageDownloader)
			// Each goroutine writes only its own index, so no lock is needed.
			if err != nil {
				errs[i] = fmt.Errorf("%s: %w", u, err)
			} else {
				results[i] = artc
			}
			return nil // do not abort other goroutines
		})
	}
	_ = g.Wait()
	return results, errs
}
