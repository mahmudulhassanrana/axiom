"""Member/detail list detection and link extraction."""

from axiom_extractors.detail_links import extract_detail_links
from axiom_extractors.models import ExtractedLink
from axiom_extractors.page_type import detect_page_type
from axiom_extractors.profile_paths import is_profile_like_path

LIST_HTML = """
<html><body>
<h1>Members</h1>
<table><tbody>
<tr><td><a href="/members/alice-smith">Alice Smith</a></td></tr>
<tr><td><a href="/members/bob-jones">Bob Jones</a></td></tr>
<tr><td><a href="/members/carol-lee">Carol Lee</a></td></tr>
</tbody></table>
</body></html>
"""

PROFILE_HTML = """
<html><body><h1>Alice Smith</h1>
<p class="designation">Director</p>
<p>alice@example.com</p></body></html>
"""


def test_detect_small_member_table_as_list() -> None:
    links = [
        ExtractedLink(href="/members/alice-smith", text="Alice Smith"),
        ExtractedLink(href="/members/bob-jones", text="Bob Jones"),
        ExtractedLink(href="/members/carol-lee", text="Carol Lee"),
    ]
    pt = detect_page_type(
        url="https://example.org/members",
        html=LIST_HTML,
        links=links,
        metadata=None,
    )
    assert pt == "list"


def test_extract_detail_links_from_table() -> None:
    links = [
        ExtractedLink(href="/members/alice-smith", text="Alice Smith"),
        ExtractedLink(href="/members/bob-jones", text="Bob Jones"),
    ]
    urls = extract_detail_links(
        html=LIST_HTML,
        page_url="https://example.org/members",
        seed_url="https://example.org/members",
        links=links,
    )
    assert len(urls) >= 2
    assert any("alice-smith" in u for u in urls)
    assert any("bob-jones" in u for u in urls)


def test_company_profile_path() -> None:
    assert is_profile_like_path("/company-profile/03-09-017")
    assert is_profile_like_path("https://basis.org.bd/company-profile/05-03-139")


def test_detect_profile_page() -> None:
    pt = detect_page_type(
        url="https://example.org/members/alice-smith",
        html=PROFILE_HTML,
        links=[],
        metadata=None,
    )
    assert pt == "profile"
