from alikindoi.enrichment import annualize, extract_tags, parse_seniority


class TestParseSeniority:
    def test_senior(self):
        assert parse_seniority("Senior Python Developer") == "senior"
        assert parse_seniority("Sr Backend Engineer") == "senior"

    def test_junior(self):
        assert parse_seniority("Junior Frontend Developer") == "junior"
        assert parse_seniority("Graduate Software Engineer") == "junior"

    def test_lead(self):
        assert parse_seniority("Lead Data Engineer") == "lead"
        assert parse_seniority("Principal Architect") == "lead"

    def test_mid(self):
        assert parse_seniority("Mid-level QA Engineer") == "mid"

    def test_unknown(self):
        assert parse_seniority("Software Engineer") is None


class TestAnnualize:
    def test_yearly_passthrough(self):
        assert annualize(42000, "yearly") == 42000

    def test_monthly(self):
        assert annualize(3000, "monthly") == 36000

    def test_hourly(self):
        assert annualize(25, "hourly") == 52000

    def test_none(self):
        assert annualize(None, "yearly") is None
        assert annualize(100, None) is None


class TestExtractTags:
    def test_finds_known_tags(self):
        tags = extract_tags(
            "Backend Developer",
            "Experience with Python, Docker and PostgreSQL required.",
        )
        assert "python" in tags
        assert "docker" in tags
        assert "postgresql" in tags

    def test_extra_tags_included(self):
        tags = extract_tags("Dev", "", ["malaga"])
        assert "malaga" in tags

    def test_no_false_substring_matches(self):
        tags = extract_tags("R Developer", "Statistical computing in R.")
        assert "rust" not in tags
