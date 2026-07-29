from alikindoi.adapters.jobspy_adapter import JobSpyAdapter, _parse_location
from alikindoi.config import SearchProfile


class TestParseLocation:
    def test_string_location(self):
        assert _parse_location("Málaga, AN, ES") == ("Málaga", "AN", "ES")

    def test_city_only(self):
        assert _parse_location("Madrid") == ("Madrid", None, None)

    def test_none(self):
        assert _parse_location(None) == (None, None, None)


class TestRowToPost:
    def test_full_row(self):
        adapter = JobSpyAdapter("indeed")
        profile = SearchProfile(name="p", search_term="python", is_remote=False)
        row = {
            "id": "abc123",
            "job_url": "https://indeed.com/viewjob?jk=abc123",
            "title": "Senior Python Developer",
            "company": "Acme",
            "location": "Málaga, AN, ES",
            "is_remote": False,
            "job_type": "fulltime",
            "interval": "yearly",
            "min_amount": 40000.0,
            "max_amount": 55000.0,
            "currency": "EUR",
            "description": "Hybrid role. Python, docker.",
        }
        post = adapter._row_to_post(row, profile)
        assert post is not None
        assert post.city == "Málaga"
        assert post.region == "AN"
        assert post.country == "ES"
        assert post.remote_type == "hybrid"
        assert post.job_type == "fulltime"
        assert post.salary_min == 40000.0

    def test_missing_url_returns_none(self):
        adapter = JobSpyAdapter("indeed")
        profile = SearchProfile(name="p", search_term="python")
        assert adapter._row_to_post({"title": "X"}, profile) is None
