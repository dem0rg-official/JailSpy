import sys
sys.path.insert(0, '.')

import tracker


def test_normalize_feed_and_join_uri():
    rows = tracker.normalize_feed([{
        'name': 'Museum', 'marker_name': 'Museum', 'status': 1,
        'duration': 95, 'server': {'job_id': 'abc/123', 'players': [1, 2]},
    }])
    assert len(rows) == 1
    assert rows[0].status == 'Open'
    assert rows[0].timer == '01:35'
    assert rows[0].players == '2'
    assert rows[0].join_uri.endswith('gameInstanceId=abc%2F123')


def test_nested_feed_and_region():
    rows = tracker.normalize_feed({'robberies': [{
        'marker_name': 'Bank', 'status': 2, 'server': {'job_id': 'job'},
        'region_data': {'city': 'Berlin', 'regionName': 'BE', 'country': 'DE'},
    }, {
        'marker_name': 'Closed', 'status': 3, 'server': {'job_id': 'closed'},
        'region_data': {'city': 'Paris'},
    }]})
    assert len(rows) == 1
    assert rows[0].name == 'Bank'
    assert rows[0].location == 'Berlin, BE, DE'
    assert rows[0].timer == '—'


def test_latest_server_is_selected_for_auto_join():
    rows = tracker.normalize_feed([
        {'marker_name': 'Bank', 'name': 'Bank', 'status': 1, 'timestamp': '2026-11-20T10:00:00Z', 'server': {'job_id': 'old'}},
        {'marker_name': 'Bank', 'name': 'Bank', 'status': 2, 'timestamp': '2026-11-20T10:01:00Z', 'server': {'job_id': 'new'}},
    ])
    assert tracker.latest_for_marker(rows, 'Bank').job_id == 'new'
    assert tracker.latest_for_marker(rows, 'Museum') is None


def test_server_columns_and_full_rules():
    rows = tracker.normalize_feed([{
        'name': 'Museum', 'marker_name': 'Museum', 'status': 'open',
        'timestamp': '2026-11-22T12:34:56Z',
        'server': {
            'job_id': 'full', 'player_count': 22,
            'teams': {'criminals': 16, 'cops': 3},
            'region': {'regionName': 'EU'},
        },
    }, {
        'name': 'Bank', 'marker_name': 'Bank', 'status': 1,
        'timestamp': '2026-11-22T12:35:00Z',
        'server': {'job_id': 'open', 'player_count': 4, 'criminal_count': 3, 'cop_count': 1},
    }])
    assert rows[0].opening_time == '12:34:56'
    assert rows[0].total_players == 22
    assert rows[0].criminals == 16
    assert rows[0].cops == 3
    assert rows[0].region == 'EU'
    assert rows[0].server_full is True
    assert rows[1].server_full is False


def test_join_filters_and_translations():
    rows = tracker.normalize_feed([
        {'marker_name': 'Bank', 'status': 1, 'timestamp': '2026-11-22T12:00:00Z', 'server': {'job_id': 'full', 'player_count': 20, 'criminal_count': 4, 'cop_count': 0}},
        {'marker_name': 'Bank', 'status': 2, 'timestamp': '2026-11-22T12:01:00Z', 'server': {'job_id': 'ready', 'player_count': 5, 'criminal_count': 4, 'cop_count': 1}},
    ])
    filters = tracker.JoinFilters(skip_full=True, only_open=True)
    assert tracker.latest_for_marker(rows, 'Bank', filters) is None
    filters.only_open = False
    assert tracker.latest_for_marker(rows, 'Bank', filters).job_id == 'ready'
    assert tracker.Translator('en')('status_active') == 'Active'
    assert tracker.Translator('ru')('status_active') == 'Активно'


def test_iso_timestamps_are_sorted_chronologically():
    rows = tracker.normalize_feed([
        {'marker_name': 'Bank', 'status': 1, 'timestamp': '2026-11-22T10:00:00Z', 'server': {'job_id': 'old'}},
        {'marker_name': 'Bank', 'status': 1, 'timestamp': '2026-11-22T11:00:00+01:00', 'server': {'job_id': 'same'}},
        {'marker_name': 'Bank', 'status': 1, 'timestamp': '2026-11-22T10:01:00Z', 'server': {'job_id': 'new'}},
    ])
    assert tracker.latest_for_marker(rows, 'Bank').job_id == 'new'



def test_russian_layout_maps_to_hotkeys():
    assert tracker.normalize_key("й") == "q"
    assert tracker.normalize_key("ф") == "a"
    assert tracker.normalize_key("в") == "d"
    assert tracker.normalize_key("а") == "f"
    assert tracker.normalize_key("о") == "j"
    assert tracker.normalize_key("щ") == "o"
    assert tracker.normalize_key("т") == "n"
    assert tracker.normalize_key("з") == "p"
    assert tracker.normalize_key("с") == "c"
    assert tracker.normalize_key("к") == "r"
    assert tracker.normalize_key("D") == "d"


def test_latest_for_marker_skips_last_job():
    import tracker
    def row(job, ts):
        return tracker.Robbery("n", "m", "Open", 1, "", job, "", "", 10, 1, 1, "", False, ts, {})
    rows = [row("a", "2026-01-01T00:00:02Z"), row("b", "2026-01-01T00:00:01Z")]
    assert tracker.latest_for_marker(rows, "m").job_id == "a"
    assert tracker.latest_for_marker(rows, "m", exclude_job="a").job_id == "b"
    assert tracker.latest_for_marker(rows[:1], "m", exclude_job="a") is None


def test_normalize_muffin_feed():
    import tracker
    data = [
        {"_id": "s1", "lastUpdated": "2026-01-01T10:20:30Z",
         "ServerInfo": {"JobID": "job-1", "CrimCount": 3, "PoliceCount": 2},
         "RegionData": {"geolocation": {"city": "Paris", "country": "France"}},
         "RobberyData": {"2": {"Descs": {"Status": "Open!"}}, "3": {"Descs": {"Status": "In Robbery"}}, "4": {"Descs": {"Status": "Closed"}}}},
        {"_id": "s2", "ServerInfo": {}, "RobberyData": {"1": {"Descs": {"Status": "Open"}}}},
    ]
    rows = tracker.normalize_muffin_feed({"servers": data})
    assert [(r.name, r.status_code) for r in rows] == [("Jewelry Store", 1), ("Museum", 2)]
    assert rows[0].job_id == "job-1" and rows[0].source_id == "s1"
    assert rows[0].total_players == 5 and rows[0].region == "Paris, France"
    assert rows[0].opening_time == "10:20:30" and rows[0].joinable


def test_table_keeps_full_server_id_and_has_no_region():
    t = tracker.Translator("en")
    columns = tracker._table_columns(t, 130)
    titles = [title for title, _ in columns]
    assert "Region" not in titles
    assert dict(columns)["Server"] >= 36


def test_english_ui_has_no_cyrillic():
    import re
    t = tracker.Translator("en")
    for key in tracker.TRANSLATIONS["en"]:
        if key in ("russian", "choose_language", "wizard_title"):
            continue
        assert not re.search("[А-Яа-я]", t(key) if "{" not in tracker.TRANSLATIONS["en"][key] else tracker.TRANSLATIONS["en"][key]), key
    assert tracker._status(1)[0] == "Open"
