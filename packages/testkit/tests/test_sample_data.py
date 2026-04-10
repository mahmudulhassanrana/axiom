from axiom_testkit import sample_data as sd


def test_deterministic_uuids() -> None:
    assert str(sd.SAMPLE_ORGANIZATION_ID).startswith("00000000")
    assert sd.SAMPLE_ORGANIZATION_ID != sd.SAMPLE_USER_ID


def test_sample_job_create_body() -> None:
    body = sd.sample_job_create_body()
    assert body["engine"] == "html_requests"
    assert body["url"] == sd.SAMPLE_URL
