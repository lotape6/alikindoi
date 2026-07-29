from alikindoi.salary_parser import _to_number, parse_salary_from_text


class TestToNumber:
    def test_dot_thousands(self):
        assert _to_number("30.184") == 30184

    def test_comma_thousands(self):
        assert _to_number("43,106") == 43106

    def test_plain(self):
        assert _to_number("45000") == 45000

    def test_k_suffix(self):
        assert _to_number("45k") == 45000
        assert _to_number("45.5K") == 45500

    def test_decimals(self):
        assert _to_number("1.234,56") == 1234.56
        assert _to_number("1,234.56") == 1234.56


class TestParseSalaryFromText:
    def test_real_world_jobspy_markdown_escaped(self):
        """The exact format found in the HASKONING postings."""
        text = "a competitive base salary (€ 30,184\\- € 43,106 p/a) and personal allowance"
        s = parse_salary_from_text(text)
        assert s is not None
        assert (s.min, s.max) == (30184, 43106)
        assert s.currency == "EUR"
        assert s.interval == "yearly"

    def test_spanish_format(self):
        text = "Salario: De 30.184 € a 43.106 € al año según experiencia"
        s = parse_salary_from_text(text)
        assert s is not None
        assert (s.min, s.max, s.currency, s.interval) == (30184, 43106, "EUR", "yearly")

    def test_spanish_monthly(self):
        text = "Sueldo entre 2.000€ y 2.500€ al mes"
        s = parse_salary_from_text(text)
        assert s is not None
        assert (s.min, s.max, s.interval) == (2000, 2500, "monthly")

    def test_us_dollars(self):
        text = "The salary range for this role is $100,000 - $150,000 per year."
        s = parse_salary_from_text(text)
        assert s is not None
        assert (s.min, s.max, s.currency) == (100000, 150000, "USD")

    def test_k_suffix_pounds(self):
        text = "Salary: £40k - £50k per annum depending on experience"
        s = parse_salary_from_text(text)
        assert s is not None
        assert (s.min, s.max, s.currency) == (40000, 50000, "GBP")

    def test_hourly(self):
        text = "Ofrecemos un salario de 25€ - 35€/hora"
        s = parse_salary_from_text(text)
        assert s is not None
        assert (s.min, s.max, s.interval) == (25, 35, "hourly")

    def test_up_to_single_bound(self):
        text = "Competitive salary up to 60.000€ depending on experience"
        s = parse_salary_from_text(text)
        assert s is not None
        assert s.max == 60000

    def test_no_salary_context_rejected(self):
        """Numbers without salary context must not be picked up."""
        text = "We have 25,000 users and process 100,000 - 200,000 events daily."
        assert parse_salary_from_text(text) is None

    def test_none_and_empty(self):
        assert parse_salary_from_text(None) is None
        assert parse_salary_from_text("") is None

    def test_implausible_rejected(self):
        text = "salary of 5 - 10 euros"  # too small to be a real salary
        assert parse_salary_from_text(text) is None
