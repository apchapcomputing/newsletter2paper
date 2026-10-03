package pdf

import (
	"strings"
	"testing"
	"time"

	art "pdf-maker/internal/article"
)

func TestEscapeTypstContent_EscapesEverythingTypstTreatsAsMarkup(t *testing.T) {
	in := `Q&A: #1 $5 @bob a_b *c* ` + "`d`" + ` <e> =f [g] \h`
	want := `Q&A: \#1 \$5 \@bob a\_b \*c\* ` + "\\`d\\`" + ` \<e\> \=f \[g\] \\h`
	if got := escapeTypstContent(in); got != want {
		t.Errorf("\n got: %s\nwant: %s", got, want)
	}
}

func TestEscapeTypstContent_LeavesOrdinaryTextAlone(t *testing.T) {
	in := "Café — “quoted” text, 100% (fine). Ünï"
	if got := escapeTypstContent(in); got != in {
		t.Errorf("got %q", got)
	}
}

func TestAddDropCap_WrapsFirstProseParagraphAndAbsorbsTheNext(t *testing.T) {
	body := "= Heading\n\nFirst short para.\n\nSecond para.\n\nThird para."

	got := addDropCap(body)

	if !strings.HasPrefix(got, "= Heading\n\n#dropcap(") {
		t.Errorf("heading must stay first and be followed by the drop cap:\n%s", got)
	}
	if !strings.Contains(got, "[\nFirst short para.\nSecond para.\n]") {
		t.Errorf("first two prose paragraphs should share the drop cap:\n%s", got)
	}
	if !strings.HasSuffix(got, "\n\nThird para.") {
		t.Errorf("later paragraphs must be untouched:\n%s", got)
	}
}

func TestAddDropCap_DoesNotAbsorbADirectiveOrHeadingFollowingTheParagraph(t *testing.T) {
	got := addDropCap("Only para.\n\n=== Next section\n\nMore.")
	if strings.Contains(got, "=== Next section\n]") || !strings.Contains(got, "\n\n=== Next section") {
		t.Errorf("heading was swallowed into the drop cap:\n%s", got)
	}
}

func TestAddDropCap_NothingEligibleReturnsBodyUnchanged(t *testing.T) {
	for _, body := range []string{"", "= Only a heading", "#figure(\n  image(\"a\"),\n)"} {
		if got := addDropCap(body); got != body {
			t.Errorf("%q changed to %q", body, got)
		}
	}
}

func testArticles() []*art.Article {
	return []*art.Article{
		{Title: "Cost of #1", Author: "Ada", Publication: "The Letter", PubDate: time.Date(2026, 3, 1, 0, 0, 0, 0, time.UTC),
			Content: "<p>First body.</p><p>More.</p>"},
		{Title: "Second", Content: "<p>Other body.</p>"},
	}
}

func TestAssembleTypst_RequiresArticles(t *testing.T) {
	if _, err := AssembleNewspaperTypst(nil, "T"); err == nil {
		t.Error("newspaper: expected error")
	}
	if _, err := AssembleEssayTypst(nil, "T"); err == nil {
		t.Error("essay: expected error")
	}
}

func TestAssembleTypst_ContainsEveryArticleWithEscapedTitleAndBylineOnlyWhenKnown(t *testing.T) {
	for name, fn := range map[string]func([]*art.Article, string) (string, error){
		"newspaper": AssembleNewspaperTypst,
		"essay":     AssembleEssayTypst,
	} {
		t.Run(name, func(t *testing.T) {
			doc, err := fn(testArticles(), "My Issue")
			if err != nil {
				t.Fatal(err)
			}
			for _, want := range []string{
				`== Cost of \#1 <article-1>`, `== Second <article-2>`,
				"First body.", "Other body.",
				"Ada · The Letter · March 1, 2026",
			} {
				if !strings.Contains(doc, want) {
					t.Errorf("missing %q", want)
				}
			}
			bodies := doc[strings.Index(doc, "== Cost"):] // skip masthead / table of contents
			if n := strings.Count(bodies, `style: "italic"`); n != 1 {
				t.Errorf("want exactly one byline (article 1 only), found %d", n)
			}
		})
	}
}

func TestAssembleTypst_LayoutsDiffer(t *testing.T) {
	news, _ := AssembleNewspaperTypst(testArticles(), "T")
	essay, _ := AssembleEssayTypst(testArticles(), "T")

	if !strings.Contains(news, "columns: 3") || !strings.Contains(news, "flipped: true") {
		t.Error("newspaper must be 3-column landscape")
	}
	if strings.Contains(essay, "columns: 3") || strings.Contains(essay, "flipped: true") {
		t.Error("essay must be single-column portrait")
	}
	if !strings.Contains(news, "#dropcap(") {
		t.Error("newspaper should use drop caps")
	}
	if strings.Contains(essay, "#dropcap(") {
		t.Error("essay must not use drop caps")
	}
}

func TestAssembleTypst_RemoveImagesAppliesPerArticle(t *testing.T) {
	arts := []*art.Article{
		{Title: "NoImg", RemoveImages: true, Content: `<p>a</p><figure><img src="/i/one.jpg"></figure>`},
		{Title: "Img", Content: `<p>b</p><figure><img src="/i/two.jpg"></figure>`},
	}
	doc, err := AssembleEssayTypst(arts, "T")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(doc, "one.jpg") {
		t.Error("image of an article with RemoveImages must be omitted")
	}
	if !strings.Contains(doc, "two.jpg") {
		t.Error("other articles keep their images")
	}
}
