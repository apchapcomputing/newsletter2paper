package fetch

import (
	"regexp"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	art "pdf-maker/internal/article"
	"net/url"
)

func init() {
	extractors = append([]platformExtractor{{
		Name: PlatformSubstack,
		DetectURL: func(rawURL string) bool {
			return strings.Contains(strings.ToLower(rawURL), "substack.com")
		},
		DetectHTML: func(doc *goquery.Document) bool {
			gen := doc.Find("meta[name='generator']").AttrOr("content", "")
			if strings.Contains(strings.ToLower(gen), "substack") {
				return true
			}
			return doc.Find("div.available-content").Length() > 0
		},
		Extract: extractSubstack,
	}}, extractors...)
}

func extractSubstack(doc *goquery.Document, rawURL string, a *art.Article) {
	a.Title = strings.TrimSpace(doc.Find("h1.post-title.published").First().Text())
	a.Subtitle = strings.TrimSpace(doc.Find("h3.subtitle").First().Text())
	a.Author = substackAuthor(doc)
	a.Publication = substackPublication(doc, rawURL)

	if ts := doc.Find("meta[property='article:published_time']").AttrOr("content", ""); ts != "" {
		if t, e := time.Parse(time.RFC3339, ts); e == nil {
			a.PubDate = t
		}
	}
	if a.PubDate.IsZero() {
		if tEl := doc.Find("time").First(); tEl.Length() > 0 {
			if dt, ok := tEl.Attr("datetime"); ok {
				if t, e := time.Parse(time.RFC3339, dt); e == nil {
					a.PubDate = t
				}
			}
		}
	}
	if a.PubDate.IsZero() {
		if dateStr := substackDateInByline(doc); dateStr != "" {
			if t, e := time.Parse("Jan 02, 2006", dateStr); e == nil {
				a.PubDate = t
			}
		}
	}

	if sel := doc.Find("div.available-content").First(); sel.Length() > 0 {
		if inner, e := sel.Html(); e == nil {
			a.Content = inner
		}
	}
	if a.Content == "" {
		if sel := doc.Find("div#entry").First(); sel.Length() > 0 {
			if inner, e := sel.Html(); e == nil {
				a.Content = inner
			}
		}
	}
}

var substackDatePattern = regexp.MustCompile(`\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{2}, \d{4}\b`)

func substackDateInByline(doc *goquery.Document) string {
	var found string
	doc.Find("div.byline-wrapper").First().Find("div,span").EachWithBreak(func(_ int, s *goquery.Selection) bool {
		text := strings.TrimSpace(s.Text())
		if text == "" {
			return true
		}
		if substackDatePattern.MatchString(text) {
			found = substackDatePattern.FindString(text)
			return false
		}
		return true
	})
	return found
}

func substackAuthor(doc *goquery.Document) string {
	if v := strings.TrimSpace(doc.Find("div.byline-wrapper a.pencraft").First().Text()); v != "" {
		return normalizeName(v)
	}
	if v := strings.TrimSpace(doc.Find(".profile-hover-card-target a").First().Text()); v != "" {
		return normalizeName(v)
	}
	if v := strings.TrimSpace(doc.Find("meta[name='author']").AttrOr("content", "")); v != "" {
		return normalizeName(v)
	}
	return ""
}

func substackPublication(doc *goquery.Document, pageURL string) string {
	if v := strings.TrimSpace(doc.Find("h1.title-oOnUGd a").First().Text()); v != "" {
		return normalizePublication(v)
	}
	if v := strings.TrimSpace(doc.Find("h1.title-oOnUGd").First().Text()); v != "" {
		return normalizePublication(v)
	}
	if v, ok := doc.Find("h1.title-oOnUGd img[alt]").First().Attr("alt"); ok && strings.TrimSpace(v) != "" {
		return normalizePublication(v)
	}
	if v := strings.TrimSpace(doc.Find("meta[property='og:site_name']").AttrOr("content", "")); v != "" {
		return normalizePublication(v)
	}
	if v := strings.TrimSpace(doc.Find("meta[name='twitter:site']").AttrOr("content", "")); v != "" {
		return normalizePublication(strings.TrimPrefix(v, "@"))
	}
	if u, e := url.Parse(pageURL); e == nil {
		host := u.Hostname()
		parts := strings.Split(host, ".")
		if len(parts) > 0 {
			return normalizePublication(strings.Title(parts[0])) //nolint:staticcheck
		}
	}
	return ""
}

// normalizeName title-cases a simple name string.
func normalizeName(name string) string {
	if name == "" {
		return name
	}
	parts := strings.Fields(name)
	for i, p := range parts {
		if len(p) == 0 {
			continue
		}
		parts[i] = strings.ToUpper(p[:1]) + strings.ToLower(p[1:])
	}
	return strings.Join(parts, " ")
}

// normalizePublication fixes curly apostrophes and trims whitespace.
func normalizePublication(s string) string {
	s = strings.TrimSpace(s)
	s = strings.ReplaceAll(s, "’", "'")
	return s
}
