"""Unit tests for CSV parser and validation logic."""

from app.services.csv_validator import parse_and_validate_csv_content, validate_csv_preview


def test_valid_csv_parsing():
    content = """name,address,phone
City Hospital,123 Main St,555-1234
Metro Care,456 Market Ave,555-5678
"""
    records, errors = parse_and_validate_csv_content(content)
    assert len(errors) == 0
    assert len(records) == 2
    assert records[0].name == "City Hospital"
    assert records[0].address == "123 Main St"
    assert records[0].phone == "555-1234"
    assert records[0].row == 1


def test_valid_csv_without_phone():
    content = """name,address
St Jude,789 Broad St
Grace Clinic,101 Pine St
"""
    records, errors = parse_and_validate_csv_content(content)
    assert len(errors) == 0
    assert len(records) == 2
    assert records[0].phone is None
    assert records[1].phone is None


def test_missing_required_headers():
    content = """title,location,phone
Hospital One,Street One,555-1111
"""
    records, errors = parse_and_validate_csv_content(content)
    assert len(records) == 0
    assert any("Missing required CSV header: 'name'" in err for err in errors)
    assert any("Missing required CSV header: 'address'" in err for err in errors)


def test_max_20_hospitals_boundary_pass():
    rows = ["name,address,phone"]
    for i in range(1, 21):
        rows.append(f"Hospital {i},Address {i},555-{i:04d}")
    content = "\n".join(rows)

    records, errors = parse_and_validate_csv_content(content)
    assert len(errors) == 0
    assert len(records) == 20


def test_max_20_hospitals_boundary_fail():
    rows = ["name,address,phone"]
    for i in range(1, 22):  # 21 rows
        rows.append(f"Hospital {i},Address {i},555-{i:04d}")
    content = "\n".join(rows)

    records, errors = parse_and_validate_csv_content(content)
    assert any("exceeds the maximum limit of 20 hospitals" in err for err in errors)


def test_empty_content():
    records, errors = parse_and_validate_csv_content("")
    assert len(records) == 0
    assert "CSV file is empty." in errors


def test_empty_rows_detection():
    content = """name,address,phone
,123 Main St,555-1234
City Care,,555-5678
"""
    records, errors = parse_and_validate_csv_content(content)
    assert len(records) == 0
    assert any("Row 1: 'name' cannot be empty" in err for err in errors)
    assert any("Row 2: 'address' cannot be empty" in err for err in errors)


def test_validate_csv_preview_helper():
    content = """name,address,phone
Hospital Alpha,Alpha St,555-0001
"""
    result = validate_csv_preview(content)
    assert result.valid is True
    assert result.total_rows == 1
    assert result.max_allowed_rows == 20
    assert len(result.preview) == 1
    assert result.preview[0]["name"] == "Hospital Alpha"
