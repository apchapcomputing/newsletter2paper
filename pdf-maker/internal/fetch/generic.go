package fetch

import (
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	art "pdf-maker/internal/article"
)

func init() {
	// Generic is always last — append, not prepend
	extractors = append(extractors, platformExtractor{
		Name:       PlatformGeneric,
		DetectURL:  nil, // never chosen by URL
		DetectHTML: func(_ *goquery.Document) bool { return true }, // always matches as fallback
		Extract:    extractGeneric,
	})
}

func extractGeneric(doc *goquery.Document, _ string, a *art.Article) {
	// Title: og:title → first h1 → <title> tag
	if v := strings.TrimSpace(doc.Find("meta[property='og:title']").AttrOr("content", "")); v != "" {
		a.Title = v
	} else if v := strings.TrimSpace(doc.Find("h1").First().Text()); v != "" {
		a.Title = v
	} else {
		a.Title = strings.TrimSpace(doc.Find("title").First().Text())
	}

	// Author
	for _, sel := range []string{"meta[name='author']", "meta[property='article:author']"} {
		if v := strings.TrimSpace(doc.Find(sel).AttrOr("content", "")); v != "" {
			a.Author = normalizeName(v)
			break
		}
	}

	// Publication
	if v := strings.TrimSpace(doc.Find("meta[property='og:site_name']").AttrOr("content", "")); v != "" {
		a.Publication = normalizePublication(v)
	}

	// Date
	if ts := doc.Find("meta[property='article:published_time']").AttrOr("content", ""); ts != "" {
		if t, e := time.Parse(time.RFC3339, ts); e == nil {
			a.PubDate = t
		}
	}
	if a.PubDate.IsZero() {
		if el := doc.Find("time[datetime]").First(); el.Length() > 0 {
			if dt, ok := el.Attr("datetime"); ok {
				if t, e := time.Parse(time.RFC3339, dt); e == nil {
					a.PubDate = t
				}
			}
		}
	}

	// Body: article → main → .content → #content — pick longest non-empty
	best := ""
	for _, sel := range []string{"article", "main", ".content", "#content", ".post-body", ".entry-content"} {
		if el := doc.Find(sel).First(); el.Length() > 0 {
			if inner, e := el.Html(); e == nil && len(inner) > len(best) {
				best = inner
			}
		}
	}
	a.Content = best
}
