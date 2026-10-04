package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"pdf-maker/internal/media"
)

func TestParseURLs(t *testing.T) {
	cases := map[string][]string{
		"":                        {},
		"  ,, ":                   {},
		"https://a":               {"https://a"},
		" https://a , https://b,": {"https://a", "https://b"},
	}
	for in, want := range cases {
		if got := parseURLs(in); !reflect.DeepEqual(got, want) {
			t.Errorf("parseURLs(%q) = %v, want %v", in, got, want)
		}
	}
}

func writeIssueJSON(t *testing.T, issue map[string]any) string {
	t.Helper()
	data, err := json.Marshal(issue)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "issue.json")
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

func articleServer(t *testing.T, broken ...string) *httptest.Server {
	t.Helper()
	failing := map[string]bool{}
	for _, b := range broken {
		failing[b] = true
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if failing[r.URL.Path] {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		name := strings.TrimPrefix(r.URL.Path, "/")
		_, _ = w.Write([]byte(`<html><body><div class="available-content"><p>body of ` + name + `</p></div></body></html>`))
	}))
	t.Cleanup(srv.Close)
	return srv
}

func newDownloader(t *testing.T) *media.Downloader {
	t.Helper()
	d, err := media.NewDownloader(filepath.Join(t.TempDir(), "images"))
	if err != nil {
		t.Fatal(err)
	}
	return d
}

func TestProcessArticlesFromJSON_ProvidedContentIsUsedWithoutFetching(t *testing.T) {
	path := writeIssueJSON(t, map[string]any{
		"issue_title": "Weekly", "layout_type": "essay",
		"articles": []map[string]any{{"title": "A", "content": "<p>provided</p>"}},
	})

	arts, errs, layout, title := processArticlesFromJSON(context.Background(), path, newDownloader(t), 2)

	if len(errs) != 0 || len(arts) != 1 || arts[0].Content != "<p>provided</p>" {
		t.Fatalf("arts=%v errs=%v", arts, errs)
	}
	if layout != "essay" || title != "Weekly" {
		t.Errorf("layout/title = %q/%q", layout, title)
	}
}

func TestProcessArticlesFromJSON_LayoutDefaultsToNewspaper(t *testing.T) {
	path := writeIssueJSON(t, map[string]any{"articles": []map[string]any{{"title": "A", "content": "<p>x</p>"}}})
	_, _, layout, _ := processArticlesFromJSON(context.Background(), path, newDownloader(t), 1)
	if layout != "newspaper" {
		t.Errorf("layout = %q", layout)
	}
}

func TestProcessArticlesFromJSON_ArticleWithNeitherContentNorURLIsReportedAndDropped(t *testing.T) {
	path := writeIssueJSON(t, map[string]any{"articles": []map[string]any{
		{"title": "Empty"}, {"title": "Fine", "content": "<p>x</p>"},
	}})

	arts, errs, _, _ := processArticlesFromJSON(context.Background(), path, newDownloader(t), 1)

	if len(arts) != 1 || arts[0].Title != "Fine" {
		t.Errorf("arts = %v", arts)
	}
	if len(errs) != 1 || !strings.Contains(errs[0].Error(), "Empty") {
		t.Errorf("errs = %v", errs)
	}
}

// Fetched content must land on the article it was fetched for, even when an earlier
// URL fails. Otherwise a reader gets article B's text under article A's headline.
func TestProcessArticlesFromJSON_FetchedContentStaysWithItsOwnArticleWhenAnEarlierFetchFails(t *testing.T) {
	srv := articleServer(t, "/one")
	path := writeIssueJSON(t, map[string]any{"articles": []map[string]any{
		{"title": "Title One", "content_url": srv.URL + "/one"},
		{"title": "Title Two", "content_url": srv.URL + "/two"},
		{"title": "Title Three", "content_url": srv.URL + "/three"},
	}})

	arts, errs, _, _ := processArticlesFromJSON(context.Background(), path, newDownloader(t), 3)

	got := map[string]string{}
	for _, a := range arts {
		got[a.Title] = a.Content
	}
	if len(arts) != 2 {
		t.Fatalf("want the 2 working articles, got %d: %v", len(arts), got)
	}
	if !strings.Contains(got["Title Two"], "body of two") {
		t.Errorf("Title Two has wrong content: %q", got["Title Two"])
	}
	if !strings.Contains(got["Title Three"], "body of three") {
		t.Errorf("Title Three has wrong content: %q", got["Title Three"])
	}
	if _, present := got["Title One"]; present {
		t.Error("the article whose fetch failed must be dropped, not filled with another article's text")
	}
	if len(errs) != 1 || !strings.Contains(errs[0].Error(), "/one") {
		t.Errorf("errs = %v", errs)
	}
}

func TestProcessArticlesFromJSON_ProvidedMetadataWinsOverFetchedMetadata(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`<html><head><meta name="author" content="page author"></head><body>
			<h1 class="post-title published">Page Title</h1><div class="available-content"><p>x</p></div></body></html>`))
	}))
	defer srv.Close()
	path := writeIssueJSON(t, map[string]any{"articles": []map[string]any{
		{"title": "", "author": "Given Author", "content_url": srv.URL},
	}})

	arts, _, _, _ := processArticlesFromJSON(context.Background(), path, newDownloader(t), 1)

	if len(arts) != 1 || arts[0].Title != "Page Title" || arts[0].Author != "Given Author" {
		t.Errorf("title/author = %q/%q", arts[0].Title, arts[0].Author)
	}
}
