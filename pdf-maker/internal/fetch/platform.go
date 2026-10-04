package fetch

import (
	"strings"

	"github.com/PuerkitoBio/goquery"
	art "pdf-maker/internal/article"
)

// Platform identifies the publishing platform for an article URL.
type Platform string

const (
	PlatformSubstack Platform = "substack"
	PlatformGhost    Platform = "ghost"
	PlatformBeehiiv  Platform = "beehiiv"
	PlatformGeneric  Platform = "generic"
)

type platformExtractor struct {
	Name       Platform
	DetectURL  func(rawURL string) bool
	DetectHTML func(doc *goquery.Document) bool
	Extract    func(doc *goquery.Document, rawURL string, a *art.Article)
}

// extractors is ordered most-specific first; generic always matches last.
var extractors []platformExtractor

// DetectPlatform returns the platform for a URL + parsed document.
// hint, when non-empty, skips detection entirely.
func DetectPlatform(hint, rawURL string, doc *goquery.Document) Platform {
	if hint != "" {
		return Platform(strings.ToLower(hint))
	}
	// URL-pattern pass (cheap, no DOM traversal)
	for _, e := range extractors {
		if e.DetectURL != nil && e.DetectURL(rawURL) {
			return e.Name
		}
	}
	// HTML fingerprint pass
	for _, e := range extractors {
		if e.DetectHTML != nil && e.DetectHTML(doc) {
			return e.Name
		}
	}
	return PlatformGeneric
}

// dispatchExtract calls the Extract function registered for the given platform.
func dispatchExtract(p Platform, doc *goquery.Document, rawURL string, a *art.Article) {
	for _, e := range extractors {
		if e.Name == p {
			e.Extract(doc, rawURL, a)
			return
		}
	}
	// Fall through to generic if platform not registered
	for _, e := range extractors {
		if e.Name == PlatformGeneric {
			e.Extract(doc, rawURL, a)
			return
		}
	}
}
