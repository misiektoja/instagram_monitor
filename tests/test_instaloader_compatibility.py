"""Offline tests for the tool's patches on Instaloader methods, which must accept every argument newer releases pass."""

from instaloader.instaloadercontext import InstaloaderContext


# Replaces Instaloader's doc_id query with a recorder, installs the tool's patch on top of it and returns the recorded
# calls with a context to query through. The context is never initialised, since no request leaves the recorder
def _patched_query(im_module, monkeypatch):
    calls = []

    def original(self, doc_id, variables, referer=None, web_api=False):
        calls.append((doc_id, variables, referer, web_api))
        return {"data": {}}

    monkeypatch.setattr(InstaloaderContext, "doc_id_graphql_query", original)
    monkeypatch.setattr(im_module, "_INSTALOADER_GRAPHQL_PROFILE_PATCH_APPLIED", False)
    im_module._apply_instaloader_graphql_profile_patch()
    return calls, InstaloaderContext.__new__(InstaloaderContext)


class TestTheGraphqlPatchPassesEveryArgument:
    # Instaloader 4.16 sends a profile's posts and reels to the web app's endpoint by passing web_api as a fourth
    # positional argument, so a patch that does not accept it fails every signed-in post check
    def test_a_positional_web_api_reaches_instaloader(self, im_module, monkeypatch):
        calls, context = _patched_query(im_module, monkeypatch)

        context.doc_id_graphql_query("29104886249145907", {"first": 12}, "https://www.instagram.com/target/", True)

        assert calls == [("29104886249145907", {"first": 12}, "https://www.instagram.com/target/", True)]

    # Callers may name the argument instead
    def test_a_keyword_web_api_reaches_instaloader(self, im_module, monkeypatch):
        calls, context = _patched_query(im_module, monkeypatch)

        context.doc_id_graphql_query("29104886249145907", {"first": 12}, referer=None, web_api=True)

        assert calls == [("29104886249145907", {"first": 12}, None, True)]

    # Older Instaloader releases still ask for the retired profile query, which the patch moves to the working one
    def test_the_retired_profile_query_is_still_rewritten(self, im_module, monkeypatch):
        calls, context = _patched_query(im_module, monkeypatch)

        context.doc_id_graphql_query("25980296051578533", {"id": "77"})

        doc_id, variables, referer, web_api = calls[0]
        assert doc_id == "27937681195819736"
        assert variables["id"] == "77" and variables["enable_integrity_filters"] is True
        assert (referer, web_api) == (None, False)
