package clean

import (
	"strings"
	"testing"
)

func typst(t *testing.T, html string, removeImages bool) string {
	t.Helper()
	out, err := HTMLToTypst(html, removeImages)
	if err != nil {
		t.Fatalf("HTMLToTypst: %v", err)
	}
	return out
}

func TestHTMLToTypst_EmptyInput(t *testing.T) {
	if got := typst(t, "  \n ", false); got != "" {
		t.Errorf("got %q, want empty", got)
	}
}

// Anything in prose that Typst treats as markup must be escaped, otherwise a
// newsletter containing "#1", "$5" or "snake_case" fails to compile or silently
// changes meaning.
func TestHTMLToTypst_EscapesTypstMarkupInText(t *testing.T) {
	got := typst(t, `<p>#1 costs $5 at foo@bar.com, a_b *x* =y &lt;tag&gt; back\slash</p>`, false)

	want := `\#1 costs \$5 at foo\@bar.com, a\_b \*x\* \=y \<tag\> back\\slash`
	if got != want {
		t.Errorf("got  %s\nwant %s", got, want)
	}
}

func TestEscapeTypst_EveryReservedCharacter(t *testing.T) {
	for _, r := range `\#$@_*<>=` + "`" {
		got := escapeTypst(string(r))
		if got != `\`+string(r) {
			t.Errorf("escapeTypst(%q) = %q, want a backslash-prefixed char", r, got)
		}
	}
	if got := escapeTypst("plain text, 123 — ünïcode"); got != "plain text, 123 — ünïcode" {
		t.Errorf("ordinary text modified: %q", got)
	}
}

func TestHTMLToTypst_HeadingLevelsStayBelowOutlineDepth(t *testing.T) {
	// h1 is the only heading allowed to reach the table of contents; body h2/h3 must be deeper.
	got := typst(t, `<h1>A</h1><h2>B</h2><h3>C</h3><h4>D</h4>`, false)

	for _, want := range []string{"= A\n", "=== B\n", "==== C\n", "===== D"} {
		if !strings.Contains(got, want) {
			t.Errorf("missing %q in:\n%s", want, got)
		}
	}
}

func TestHTMLToTypst_InlineFormattingUsesFunctionForms(t *testing.T) {
	// The function forms are required so formatting adjacent to letters ("the<em>X</em>") still parses.
	got := typst(t, `<p>the<em>Shareholder Republic</em> and <strong>bold</strong></p>`, false)

	if !strings.Contains(got, "the#emph[Shareholder Republic];") {
		t.Errorf("emphasis not in function form: %s", got)
	}
	if !strings.Contains(got, "#strong[bold];") {
		t.Errorf("strong not in function form: %s", got)
	}
}

func TestHTMLToTypst_Links(t *testing.T) {
	got := typst(t, `<p><a href="https://e.com/x">read this</a>(aside) and <a href="https://e.com/y">https://e.com/y</a></p>`, false)

	// The trailing ";" stops Typst from treating "(aside)" as call arguments.
	if !strings.Contains(got, `#link("https://e.com/x")[read this];(aside)`) {
		t.Errorf("link with label wrong: %s", got)
	}
	// A link whose text is its own URL is printed bare rather than duplicated.
	if strings.Contains(got, `#link("https://e.com/y")`) {
		t.Errorf("self-describing link should be plain text: %s", got)
	}
}

func TestHTMLToTypst_LinkWithoutTextShowsItsURL(t *testing.T) {
	got := typst(t, `<p><a href="https://e.com/z"></a></p>`, false)
	if !strings.Contains(got, "https://e.com/z") {
		t.Errorf("got %q", got)
	}
}

func TestHTMLToTypst_Images(t *testing.T) {
	html := `<figure><img src="/tmp/img/a.png" alt="x"><figcaption>A *caption*</figcaption></figure><p>t<img src="/tmp/img/b.png" alt="Alt"></p>`

	with := typst(t, html, false)
	if !strings.Contains(with, `image("/tmp/img/a.png", width: 100%)`) || !strings.Contains(with, `caption: [A \*caption\*]`) {
		t.Errorf("figure not rendered with escaped caption:\n%s", with)
	}
	if !strings.Contains(with, `image("/tmp/img/b.png"`) || !strings.Contains(with, "caption: [Alt]") {
		t.Errorf("inline img alt not used as caption:\n%s", with)
	}

	without := typst(t, html, true)
	if strings.Contains(without, "image(") || strings.Contains(without, "caption") {
		t.Errorf("removeImages=true still emitted images:\n%s", without)
	}
}

func TestHTMLToTypst_ImageWithoutSourceIsSkipped(t *testing.T) {
	if got := typst(t, `<img alt="no src"><p>text</p>`, false); strings.Contains(got, "image(") {
		t.Errorf("emitted image without src: %s", got)
	}
}

func TestHTMLToTypst_Lists(t *testing.T) {
	got := typst(t, `<ul><li>one</li><li></li><li>two</li></ul><ol><li>first</li><li>second</li></ol>`, false)

	if !strings.Contains(got, "- one\n- two\n") {
		t.Errorf("unordered list wrong (empty items must be dropped): %s", got)
	}
	if !strings.Contains(got, "1. first\n2. second\n") {
		t.Errorf("ordered list wrong: %s", got)
	}
}

func TestHTMLToTypst_BlockquotePreCodeAndRule(t *testing.T) {
	got := typst(t, `<blockquote><p>quoted</p></blockquote><pre>line1
line2</pre><hr>`, false)

	if !strings.Contains(got, "#block(stroke: (left: 2pt + gray)") || !strings.Contains(got, "quoted") {
		t.Errorf("blockquote missing: %s", got)
	}
	if !strings.Contains(got, "```\nline1\nline2\n```") {
		t.Errorf("pre block must be a verbatim raw block: %s", got)
	}
	if !strings.Contains(got, "#line(length: 100%") {
		t.Errorf("hr missing: %s", got)
	}
}

// Inside a raw (backtick) span Typst does not process escapes, so escaping would
// print literal backslashes in the reader's code sample.
func TestHTMLToTypst_InlineCodeIsVerbatim(t *testing.T) {
	got := typst(t, `<p>Call <code>snake_case_name</code> now</p>`, false)

	if !strings.Contains(got, "`snake_case_name`") {
		t.Errorf("inline code was escaped inside a raw span: %s", got)
	}
}

func TestHTMLToTypst_Table(t *testing.T) {
	got := typst(t, `<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>x_y</td></tr></table>`, false)

	if !strings.Contains(got, "columns: 2") {
		t.Errorf("column count wrong: %s", got)
	}
	for _, cell := range []string{"[A]", "[B]", "[1]", `[x\_y]`} {
		if !strings.Contains(got, cell) {
			t.Errorf("missing cell %s in: %s", cell, got)
		}
	}
}

func TestHTMLToTypst_UnknownAndWrapperElementsKeepTheirText(t *testing.T) {
	got := typst(t, `<section><div><span>kept</span> <custom-tag>also kept</custom-tag></div></section>`, false)
	if !strings.Contains(got, "kept") || !strings.Contains(got, "also kept") {
		t.Errorf("text lost: %q", got)
	}
}
