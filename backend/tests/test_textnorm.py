from alikindoi.textnorm import looks_like_html, normalize_description


class TestLooksLikeHtml:
    def test_html(self):
        assert looks_like_html("<p>Hello <strong>world</strong></p>")

    def test_markdown_not_html(self):
        assert not looks_like_html("# Title\n\n- item one\n- item two")

    def test_plain_not_html(self):
        assert not looks_like_html("Just plain text with 2 < 3 comparisons")


class TestNormalizeDescription:
    def test_html_to_markdown(self):
        raw = "<p>We are looking for a <strong>Python developer</strong>.</p><ul><li>Django</li><li>FastAPI</li></ul>"
        out = normalize_description(raw)
        assert "<p>" not in out
        assert "<li>" not in out
        assert "Python developer" in out
        assert "- Django" in out

    def test_jobspy_escaped_chars(self):
        raw = "Salary: € 30,184\\- € 43,106 p/a\n\nRequirements:\n\\- Python\n\\- Docker"
        out = normalize_description(raw)
        assert "\\-" not in out
        assert "30,184- € 43,106" in out or "30,184 -" in out

    def test_collapses_blank_lines(self):
        raw = "First paragraph.\n\n\n\n\nSecond paragraph."
        out = normalize_description(raw)
        assert "\n\n\n" not in out

    def test_none_passthrough(self):
        assert normalize_description(None) is None

    def test_idempotent(self):
        raw = "<p>Some <b>HTML</b> description</p>"
        once = normalize_description(raw)
        assert normalize_description(once) == once
