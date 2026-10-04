package fetch

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/PuerkitoBio/goquery"
)

const substackPage = `<!doctype html><html><head>
<meta property="og:site_name" content="Example Letter">
<meta property="article:published_time" content="2026-03-01T10:30:00Z">
</head><body>
<h1 class="post-title published">The Real Title</h1>
<h3 class="subtitle">A useful subtitle</h3>
<div class="byline-wrapper"><a class="pencraft" href="/@ada">ADA LOVELACE</a><div>Mar 01, 2026</div></div>
<div class="available-content">
  <div class="body markup">
    <p>First paragraph.</p>
    <div class="subscription-widget-wrap-editor"><form><input type="email"></form></div>
    <p>Second paragraph.</p>
  </div>
</div>
<footer>site chrome that must not be in the article</footer>
</body></html>`

func serve(t *testing.T, status int, body string) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(status)
		_, _ = w.Write([]byte(body))
	}))
	t.Cleanup(srv.Close)
	return srv
}

func TestFetchArticle_ExtractsMetadataAndBodyFromASubstackPage(t *testing.T) {
	srv := serve(t, 200, substackPage)

	a, raw, err := FetchArticle(context.Background(), srv.URL+"/p/the-real-title")
	if err != nil {
		t.Fatal(err)
	}

	if a.Title != "The Real Title" || a.Subtitle != "A useful subtitle" {
		t.Errorf("title/subtitle = %q / %q", a.Title, a.Subtitle)
	}
	if a.Author != "Ada Lovelace" {
		t.Errorf("author should be title-cased from the byline, got %q", a.Author)
	}
	if a.Publication != "Example Letter" {
		t.Errorf("publication = %q", a.Publication)
	}
	if !a.PubDate.Equal(time.Date(2026, 3, 1, 10, 30, 0, 0, time.UTC)) {
		t.Errorf("PubDate = %v", a.PubDate)
	}
	if a.Link != srv.URL+"/p/the-real-title" {
		t.Errorf("Link = %q", a.Link)
	}
	if len(raw) == 0 {
		t.Error("raw page bytes should be returned")
	}

	if !strings.Contains(a.Content, "First paragraph.") || !strings.Contains(a.Content, "Second paragraph.") {
		t.Errorf("body missing:\n%s", a.Content)
	}
	if strings.Contains(a.Content, "site chrome") {
		t.Errorf("content must come from div.available-content only:\n%s", a.Content)
	}
	if strings.Contains(a.Content, "<form") || strings.Contains(a.Content, "subscription-widget") {
		t.Errorf("subscription widget should be cleaned out:\n%s", a.Content)
	}
}

func TestFetchArticle_ContentFallsBackToEntryDivThenWholePage(t *testing.T) {
	entry := serve(t, 200, `<html><body><nav>menu</nav><div id="entry"><p>entry body</p></div></body></html>`)
	a, _, err := FetchArticle(context.Background(), entry.URL)
	if err != nil || !strings.Contains(a.Content, "entry body") || strings.Contains(a.Content, "menu") {
		t.Errorf("div#entry fallback failed: %v / %q", err, a.Content)
	}

	bare := serve(t, 200, `<html><body><p>just a page</p></body></html>`)
	a, _, err = FetchArticle(context.Background(), bare.URL)
	if err != nil || !strings.Contains(a.Content, "just a page") {
		t.Errorf("whole-page fallback failed: %v / %q", err, a.Content)
	}
}

func TestFetchArticle_DateFallbacksInPriorityOrder(t *testing.T) {
	cases := map[string]struct {
		html string
		want time.Time
	}{
		"time element": {
			`<html><body><time datetime="2026-02-03T04:05:06Z"></time><p>x</p></body></html>`,
			time.Date(2026, 2, 3, 4, 5, 6, 0, time.UTC),
		},
		"byline text": {
			`<html><body><div class="byline-wrapper"><span>by Someone</span><span>Oct 09, 2025</span></div></body></html>`,
			time.Date(2025, 10, 9, 0, 0, 0, 0, time.UTC),
		},
		"meta beats time element": {
			`<html><head><meta property="article:published_time" content="2026-01-01T00:00:00Z"></head><body><time datetime="2020-01-01T00:00:00Z"></time></body></html>`,
			time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC),
		},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			a, _, err := FetchArticle(context.Background(), serve(t, 200, tc.html).URL)
			if err != nil {
				t.Fatal(err)
			}
			if !a.PubDate.Equal(tc.want) {
				t.Errorf("PubDate = %v, want %v", a.PubDate, tc.want)
			}
		})
	}
}

func TestFetchArticle_NoDateLeavesZeroValue(t *testing.T) {
	a, _, err := FetchArticle(context.Background(), serve(t, 200, `<html><body><p>x</p></body></html>`).URL)
	if err != nil || !a.PubDate.IsZero() {
		t.Errorf("err=%v PubDate=%v", err, a.PubDate)
	}
}

func TestFetchArticle_Errors(t *testing.T) {
	if _, _, err := FetchArticle(context.Background(), ""); err == nil {
		t.Error("empty URL must error")
	}
	for _, status := range []int{403, 404, 500} {
		if _, _, err := FetchArticle(context.Background(), serve(t, status, "nope").URL); err == nil {
			t.Errorf("status %d must error", status)
		}
	}
	if _, _, err := FetchArticle(context.Background(), "http://127.0.0.1:1/unreachable"); err == nil {
		t.Error("unreachable host must error")
	}
}

func TestFetchArticle_HonoursContextCancellation(t *testing.T) {
	slow := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-r.Context().Done():
		case <-time.After(2 * time.Second):
		}
	}))
	defer slow.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	start := time.Now()
	_, _, err := FetchArticle(ctx, slow.URL)

	if err == nil || time.Since(start) > time.Second {
		t.Errorf("expected prompt cancellation, err=%v after %v", err, time.Since(start))
	}
}

func TestExtractPublication_FallbackOrder(t *testing.T) {
	cases := map[string]struct{ html, url, want string }{
		"header link beats meta":   {`<h1 class="title-oOnUGd"><a>Header Name</a></h1><meta property="og:site_name" content="OG Name">`, "https://x.example.com/p/a", "Header Name"},
		"og:site_name":             {`<meta property="og:site_name" content="OG Name">`, "https://x.example.com/p/a", "OG Name"},
		"logo-only header alt":     {`<h1 class="title-oOnUGd"><img alt="Logo Name"></h1>`, "https://x.example.com/p/a", "Logo Name"},
		"twitter handle":           {`<meta name="twitter:site" content="@handle">`, "https://x.example.com/p/a", "handle"},
		"curly apostrophe":         {"<meta property=\"og:site_name\" content=\"Kyla\u2019s Letter\">", "https://x.example.com/p/a", "Kyla's Letter"},
		"subdomain as last resort": {``, "https://kyla.substack.com/p/a", "Kyla"},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			doc, err := goquery.NewDocumentFromReader(strings.NewReader("<html><head></head><body>" + tc.html + "</body></html>"))
			if err != nil {
				t.Fatal(err)
			}
			if got := extractPublication(doc, tc.url); got != tc.want {
				t.Errorf("got %q, want %q", got, tc.want)
			}
		})
	}
}

func TestExtractAuthor_FallbackOrderAndNormalisation(t *testing.T) {
	cases := map[string]struct{ html, want string }{
		"byline link": {`<div class="byline-wrapper"><a class="pencraft">kyla SCANLON</a></div><meta name="author" content="Other">`, "Kyla Scanlon"},
		"hover card":  {`<div class="profile-hover-card-target"><a>jane doe</a></div>`, "Jane Doe"},
		"meta author": {`<meta name="author" content="sam smith">`, "Sam Smith"},
		"none":        {`<p>no author anywhere</p>`, ""},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			doc, _ := goquery.NewDocumentFromReader(strings.NewReader("<html><body>" + tc.html + "</body></html>"))
			if got := extractAuthor(doc); got != tc.want {
				t.Errorf("got %q, want %q", got, tc.want)
			}
		})
	}
}

func TestDeriveFilename(t *testing.T) {
	cases := map[string]string{
		"https://x.substack.com/p/how-ai-works":         "how-ai-works.html",
		"https://x.substack.com/p/how-ai-works/":        "how-ai-works.html",
		"https://x.substack.com/p/how-ai-works?utm=1#c": "how-ai-works.html",
		"https://x.com/post.html":                       "post.html",
		"https://x.com/a b/c&d":                         "c-d.html",
	}
	for in, want := range cases {
		if got := deriveFilename(in); got != want {
			t.Errorf("deriveFilename(%q) = %q, want %q", in, got, want)
		}
	}
	// No usable path segment: stable hash-based name, distinct per URL.
	a, b := deriveFilename("https://???/"), deriveFilename("https://!!!/")
	if !strings.HasPrefix(a, "article-") || a == b {
		t.Errorf("fallback names should be hashed and distinct: %q %q", a, b)
	}
}

func TestFetchAndSaveArticle_WritesCleanedContentToDisk(t *testing.T) {
	srv := serve(t, 200, substackPage)
	dir := filepath.Join(t.TempDir(), "nested", "out")

	path, err := FetchAndSaveArticle(context.Background(), srv.URL+"/p/saved-post", dir)
	if err != nil {
		t.Fatal(err)
	}

	if filepath.Base(path) != "saved-post.html" || !filepath.IsAbs(path) {
		t.Errorf("path = %q", path)
	}
	data, err := os.ReadFile(path)
	if err != nil || !strings.Contains(string(data), "First paragraph.") {
		t.Errorf("file content wrong: %v", err)
	}
}

func TestFetchArticlesConcurrent_KeepsOrderAndReportsFailuresWithoutAborting(t *testing.T) {
	mux := http.NewServeMux()
	page := func(title string) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			_, _ = w.Write([]byte(`<html><body><h1 class="post-title published">` + title + `</h1><div class="available-content"><p>` + title + `</p></div></body></html>`))
		}
	}
	mux.HandleFunc("/one", page("One"))
	mux.HandleFunc("/two", page("Two"))
	mux.HandleFunc("/three", page("Three"))
	mux.HandleFunc("/broken", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(500) })
	srv := httptest.NewServer(mux)
	defer srv.Close()

	urls := []string{srv.URL + "/one", srv.URL + "/broken", srv.URL + "/two", srv.URL + "/three"}
	arts, errs := FetchArticlesConcurrent(context.Background(), urls, 2)

	var titles []string
	for _, a := range arts {
		titles = append(titles, a.Title)
	}
	if strings.Join(titles, ",") != "One,Two,Three" {
		t.Errorf("order/contents = %v", titles)
	}
	if len(errs) != 1 || !strings.Contains(errs[0].Error(), "/broken") {
		t.Errorf("errors = %v", errs)
	}
}

func TestFetchArticlesConcurrent_NoURLs(t *testing.T) {
	arts, errs := FetchArticlesConcurrent(context.Background(), nil, 4)
	if arts != nil || errs != nil {
		t.Errorf("got %v %v", arts, errs)
	}
}
