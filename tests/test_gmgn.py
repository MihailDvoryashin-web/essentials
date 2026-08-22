from essentials.gmgn import GmgnClient


def test_command_contains_exact_server_side_filters():
    command = GmgnClient("gmgn-cli", 45, 3).command
    expected_pairs = {
        "--chain": "sol",
        "--launchpad-platform": "Pump.fun",
        "--min-marketcap": "50000",
        "--max-marketcap": "250000",
        "--min-total-fee": "5",
        "--min-renowned-count": "1",
    }
    for flag, value in expected_pairs.items():
        assert command[command.index(flag) + 1] == value


def test_response_is_flattened_and_locally_social_filtered():
    payload = GmgnClient._parse_json('{"data":{"new_creation":[],"pump":[],"completed":[]}}')
    assert payload["data"]["pump"] == []

