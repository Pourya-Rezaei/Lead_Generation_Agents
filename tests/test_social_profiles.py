from src.connectors.social_profiles import INSTAGRAM, TIKTOK, YOUTUBE


def test_social_connectors_are_disabled_by_default():
    assert not INSTAGRAM.enabled and not TIKTOK.enabled and not YOUTUBE.enabled


def test_mapping_allows_only_public_https_profile_fields():
    result = INSTAGRAM.map_public_profile({"profileUrl": "https://instagram.com/cafe", "username": "cafe", "bio": "business", "website": "https://cafe.example", "email": "private@example"})
    assert result and result.status == "unverified"
    assert result.title == "cafe"
    assert not hasattr(result, "email")


def test_invalid_or_personal_unstructured_result_is_ignored():
    assert TIKTOK.map_public_profile({"url": "http://tiktok.com/cafe", "username": "cafe"}) is None
    assert YOUTUBE.map_public_profile({"profileUrl": "https://youtube.com/cafe"}) is None
