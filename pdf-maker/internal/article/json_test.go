package article

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestParseArticlesJSON_RoundTripsTheFastAPIContract(t *testing.T) {
	// Field names here are what services/go_pdf_service.py sends.
	in := `{
	  "issue_id": "abc", "issue_title": "Weekly", "layout_type": "essay",
	  "articles": [{"title": "T", "subtitle": "S", "author": "A", "publication": "P",
	                "date_published": "2026-03-01T10:00:00Z", "content_url": "https://e.com/a",
	                "content": "<p>x</p>", "publication_id": "pid", "remove_images": true}]
	}`

	got, err := ParseArticlesJSON(strings.NewReader(in))
	if err != nil {
		t.Fatal(err)
	}
	if got.IssueTitle != "Weekly" || got.LayoutType != "essay" || len(got.Articles) != 1 {
		t.Fatalf("issue fields wrong: %+v", got)
	}
	a := got.Articles[0].ToArticle()
	if a.Title != "T" || a.Subtitle != "S" || a.Author != "A" || a.Publication != "P" ||
		a.Link != "https://e.com/a" || a.Content != "<p>x</p>" || !a.RemoveImages {
		t.Errorf("ToArticle mapping wrong: %+v", a)
	}
}

func TestParseArticlesJSON_Rejects(t *testing.T) {
	cases := map[string]string{
		"no articles key":   `{"issue_title": "x"}`,
		"empty articles":    `{"articles": []}`,
		"malformed json":    `{"articles": [`,
		"wrong field types": `{"articles": "nope"}`,
	}
	for name, in := range cases {
		t.Run(name, func(t *testing.T) {
			if _, err := ParseArticlesJSON(strings.NewReader(in)); err == nil {
				t.Error("expected an error")
			}
		})
	}
}

func TestLoadArticlesFromJSON(t *testing.T) {
	path := filepath.Join(t.TempDir(), "in.json")
	if err := os.WriteFile(path, []byte(`{"articles":[{"title":"T"}]}`), 0o644); err != nil {
		t.Fatal(err)
	}
	got, err := LoadArticlesFromJSON(path)
	if err != nil || got.Articles[0].Title != "T" {
		t.Fatalf("got %+v, %v", got, err)
	}
	if _, err := LoadArticlesFromJSON(filepath.Join(t.TempDir(), "missing.json")); err == nil {
		t.Error("missing file must be an error")
	}
}

func TestToArticle_DateFormats(t *testing.T) {
	want := time.Date(2026, 3, 1, 10, 30, 0, 0, time.UTC)
	cases := map[string]time.Time{
		"2026-03-01T10:30:00Z":      want,
		"2026-03-01T10:30:00.000Z":  want,
		"2026-03-01T12:30:00+02:00": want, // same instant
		"2026-03-01T10:30:00":       want, // Python isoformat() of a naive datetime
		"2026-03-01":                time.Date(2026, 3, 1, 0, 0, 0, 0, time.UTC),
	}
	for in, expected := range cases {
		a := (&ArticleInput{DatePublished: in}).ToArticle()
		if !a.PubDate.Equal(expected) {
			t.Errorf("%q parsed to %v, want %v", in, a.PubDate, expected)
		}
	}
}

func TestToArticle_UnparseableOrMissingDateLeavesZero(t *testing.T) {
	for _, in := range []string{"", "yesterday", "03/01/2026"} {
		if a := (&ArticleInput{DatePublished: in}).ToArticle(); !a.PubDate.IsZero() {
			t.Errorf("%q should leave PubDate zero, got %v", in, a.PubDate)
		}
	}
}
