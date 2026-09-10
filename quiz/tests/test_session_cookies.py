"""
Tests for HttpOnly team-token cookie storage (quiz/session_cookies.py).

This cookie is the durable half of team identity: localStorage is easily lost,
and losing it locks a player out of their own team, so the server keeps a copy
it can recognise them by with no client-side state at all.
"""

import json

from django.http import HttpResponse
from django.test import TestCase, RequestFactory, override_settings

from quiz.models import Game, GameSession, SessionTeam
from quiz.session_cookies import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    COOKIE_PATH,
    MAX_TRACKED,
    find_team_by_cookie,
    get_team_token,
    read_team_tokens,
    remember_team_token,
    resumable_sessions,
)


class ReadTeamTokensTest(TestCase):
    """The cookie is client-supplied, so reading it must never raise"""

    def setUp(self):
        self.factory = RequestFactory()

    def _request_with_cookie(self, raw):
        request = self.factory.get("/quiz/play/")
        if raw is not None:
            request.COOKIES[COOKIE_NAME] = raw
        return request

    def test_no_cookie(self):
        self.assertEqual(read_team_tokens(self._request_with_cookie(None)), {})

    def test_empty_cookie(self):
        self.assertEqual(read_team_tokens(self._request_with_cookie("")), {})

    def test_malformed_json(self):
        self.assertEqual(read_team_tokens(self._request_with_cookie("{nope")), {})

    def test_json_that_is_not_an_object(self):
        self.assertEqual(read_team_tokens(self._request_with_cookie('["a"]')), {})
        self.assertEqual(read_team_tokens(self._request_with_cookie('"a"')), {})
        self.assertEqual(read_team_tokens(self._request_with_cookie("7")), {})

    def test_non_string_values_are_dropped(self):
        raw = json.dumps({"ABC123": "tok", "DEF456": 7, "GHI789": None, "JKL012": ""})

        self.assertEqual(
            read_team_tokens(self._request_with_cookie(raw)), {"ABC123": "tok"}
        )

    def test_valid_cookie(self):
        raw = json.dumps({"ABC123": "tok1", "DEF456": "tok2"})

        self.assertEqual(
            read_team_tokens(self._request_with_cookie(raw)),
            {"ABC123": "tok1", "DEF456": "tok2"},
        )

    def test_get_team_token(self):
        request = self._request_with_cookie(json.dumps({"ABC123": "tok1"}))

        self.assertEqual(get_team_token(request, "ABC123"), "tok1")
        self.assertIsNone(get_team_token(request, "ZZZZZZ"))


class RememberTeamTokenTest(TestCase):
    """Writing the cookie: flags, ordering, and the size cap"""

    def setUp(self):
        self.factory = RequestFactory()

    def _remember(self, existing, code, token):
        request = self.factory.get("/quiz/play/")
        if existing is not None:
            request.COOKIES[COOKIE_NAME] = json.dumps(existing)
        response = HttpResponse()
        remember_team_token(response, request, code, token)
        return response

    def _cookie_payload(self, response):
        return json.loads(response.cookies[COOKIE_NAME].value)

    def test_sets_token(self):
        response = self._remember(None, "ABC123", "tok1")

        self.assertEqual(self._cookie_payload(response), {"ABC123": "tok1"})

    def test_cookie_flags(self):
        cookie = self._remember(None, "ABC123", "tok1").cookies[COOKIE_NAME]

        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["path"], COOKIE_PATH)
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["max-age"], COOKIE_MAX_AGE)

    @override_settings(SESSION_COOKIE_SECURE=True)
    def test_secure_flag_follows_session_cookie_secure(self):
        cookie = self._remember(None, "ABC123", "tok1").cookies[COOKIE_NAME]

        self.assertTrue(cookie["secure"])

    @override_settings(SESSION_COOKIE_SECURE=False)
    def test_secure_flag_off_in_development(self):
        cookie = self._remember(None, "ABC123", "tok1").cookies[COOKIE_NAME]

        self.assertFalse(cookie["secure"])

    def test_keeps_other_sessions(self):
        response = self._remember({"OLD111": "tokold"}, "NEW222", "toknew")

        self.assertEqual(
            self._cookie_payload(response),
            {"NEW222": "toknew", "OLD111": "tokold"},
        )

    def test_newest_session_is_first(self):
        response = self._remember({"OLD111": "tokold"}, "NEW222", "toknew")

        self.assertEqual(list(self._cookie_payload(response))[0], "NEW222")

    def test_replaces_token_for_same_code(self):
        response = self._remember({"ABC123": "old"}, "ABC123", "new")

        self.assertEqual(self._cookie_payload(response), {"ABC123": "new"})

    def test_caps_tracked_sessions(self):
        existing = {f"CODE{index:02d}": f"tok{index}" for index in range(MAX_TRACKED)}

        response = self._remember(existing, "FRESH1", "tokfresh")
        payload = self._cookie_payload(response)

        self.assertEqual(len(payload), MAX_TRACKED)
        self.assertEqual(list(payload)[0], "FRESH1")
        # The oldest entry is the one dropped
        self.assertNotIn(f"CODE{MAX_TRACKED - 1:02d}", payload)


class FindTeamByCookieTest(TestCase):
    """Resolving a remembered token back to a live team"""

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(subtitle="Cookie Game")
        self.session = GameSession.objects.create(game=self.game, admin_name="Host")
        self.team = SessionTeam.objects.create(session=self.session, name="Cookie Team")

    def _request(self, tokens):
        request = self.factory.get("/quiz/play/")
        request.COOKIES[COOKIE_NAME] = json.dumps(tokens)
        return request

    def test_finds_team(self):
        request = self._request({self.session.code: self.team.token})

        self.assertEqual(find_team_by_cookie(request, self.session.code), self.team)

    def test_no_cookie(self):
        request = self.factory.get("/quiz/play/")

        self.assertIsNone(find_team_by_cookie(request, self.session.code))

    def test_unknown_token(self):
        request = self._request({self.session.code: "not-a-real-token"})

        self.assertIsNone(find_team_by_cookie(request, self.session.code))

    def test_token_remembered_under_another_code_is_rejected(self):
        """A token can only recover a seat in the session it belongs to"""
        other_session = GameSession.objects.create(game=self.game, admin_name="Host 2")
        request = self._request({other_session.code: self.team.token})

        self.assertIsNone(find_team_by_cookie(request, other_session.code))

    def test_deleted_team_resolves_to_nothing(self):
        token = self.team.token
        self.team.delete()
        request = self._request({self.session.code: token})

        self.assertIsNone(find_team_by_cookie(request, self.session.code))


class ResumableSessionsTest(TestCase):
    """The list rendered on the rejoin page"""

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(subtitle="Cookie Game")
        self.session = GameSession.objects.create(game=self.game, admin_name="Host")
        self.team = SessionTeam.objects.create(session=self.session, name="Cookie Team")

    def _request(self, tokens):
        request = self.factory.get("/quiz/play/rejoin/")
        request.COOKIES[COOKIE_NAME] = json.dumps(tokens)
        return request

    def test_no_cookie(self):
        self.assertEqual(resumable_sessions(self.factory.get("/quiz/play/rejoin/")), [])

    def test_lists_session(self):
        result = resumable_sessions(self._request({self.session.code: self.team.token}))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["code"], self.session.code)
        self.assertEqual(result[0]["team_name"], "Cookie Team")
        self.assertEqual(result[0]["game_name"], self.game.name)

    def test_excludes_completed_sessions(self):
        self.session.status = GameSession.Status.COMPLETED
        self.session.save()

        result = resumable_sessions(self._request({self.session.code: self.team.token}))

        self.assertEqual(result, [])

    def test_excludes_unknown_tokens(self):
        result = resumable_sessions(self._request({self.session.code: "bogus"}))

        self.assertEqual(result, [])

    def test_excludes_code_token_mismatch(self):
        other_session = GameSession.objects.create(game=self.game, admin_name="Host 2")

        result = resumable_sessions(
            self._request({other_session.code: self.team.token})
        )

        self.assertEqual(result, [])

    def test_preserves_cookie_order(self):
        """Most recently joined first, as stored"""
        second_session = GameSession.objects.create(game=self.game, admin_name="Host 2")
        second_team = SessionTeam.objects.create(
            session=second_session, name="Second Team"
        )

        result = resumable_sessions(
            self._request(
                {
                    second_session.code: second_team.token,
                    self.session.code: self.team.token,
                }
            )
        )

        self.assertEqual(
            [entry["code"] for entry in result],
            [second_session.code, self.session.code],
        )
