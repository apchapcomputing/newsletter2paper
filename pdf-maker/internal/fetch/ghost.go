package fetch

import (
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	art "pdf-maker/internal/article"
)

func init() {
	extractors = append([]platformExtractor{{
		Name: PlatformGhost,
		DetectURL: func(rawURL string) bool {
			return strings.Contains(strings.ToLower(rawURL), "ghost.io")
		},
		DetectHTML: func(doc *goquery.Document) bool {
			gen := doc.Find("meta[name='generator']").AttrOr("content", "")
			if strings.Contains(strings.ToLower(gen), "ghost") {
				return true
			}
			return doc.Find(".gh-content").Length() > 0
		},
		Extract: extractGhost,
	}}, extractors...)
}

func extractGhost(doc *goquery.Document, _ string, a *art.Article) {
	// Title
	for _, sel := range []string{".article-title", "h1.post-title", "h1.gh-article-title"} {
		if v := strings.TrimSpace(doc.Find(sel).First().Text()); v != "" {
			a.Title = v
			break
		}
	}
	if a.Title == "" {
		a.Title = strings.TrimSpace(doc.Find("meta[property='og:title']").AttrOr("content", ""))
	}

	// Author
	for _, sel := range []string{".author-name", ".post-author", ".gh-author-name"} {
		if v := strings.TrimSpace(doc.Find(sel).First().Text()); v != "" {
			a.Author = normalizeName(v)
			break
		}
	}
	if a.Author == "" {
		a.Author = normalizeName(strings.TrimSpace(doc.Find("meta[name='author']").AttrOr("content", "")))
	}

	// Publication
	if v := strings.TrimSpace(doc.Find("meta[property='og:site_name']").AttrOr("content", "")); v != "" {
		a.Publication = normalizePublication(v)
	}

	// Date
	for _, sel := range []string{"time.published-at", "time.gh-article-date", "time"} {
		if el := doc.Find(sel).First(); el.Length() > 0 {
			if dt, ok := el.Attr("datetime"); ok {
				if t, e := time.Parse(time.RFC3339, dt); e == nil {
					a.PubDate = t
					break
				}
			}
		}
	}
	if a.PubDate.IsZero() {
		if ts := doc.Find("meta[property='article:published_time']").AttrOr("content", ""); ts != "" {
			if t, e := time.Parse(time.RFC3339, ts); e == nil {
				a.PubDate = t
			}
		}
	}

	// Body
	for _, sel := range []string{".gh-content", ".post-content", "article.post-content", ".article-body"} {
		if el := doc.Find(sel).First(); el.Length() > 0 {
			if inner, e := el.Html(); e == nil && strings.TrimSpace(inner) != "" {
				a.Content = inner
				break
			}
		}
	}
}
