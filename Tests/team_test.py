def test_create_team(test_client, mocker):
    """Test the /create_team route."""
    mock_team = mocker.patch("Service.TeamService.TeamService.create_team")
    mock_team.return_value.id = 1

    mock_season = mocker.patch("Service.SeasonService.SeasonService.find_latest_season_by_team_id")
    mock_season.return_value.id = 42

    response = test_client.post("/create_team", data={
        "team_name": "TestTeam",
        "club_name": "TestClub",
        "password": "securepass"
    })

    assert response.status_code == 200

def test_render_edit_team(test_client, mocker):
    """Test the /render/edit_team route."""
    mock_verify_login = mocker.patch("Service.TeamService.TeamService.verify_login")
    mock_verify_login.return_value.id = 1

    mock_season = mocker.patch("Service.SeasonService.SeasonService.find_latest_season_by_team_id")
    mock_season.return_value.id = 42

    response = test_client.post("/render/edit_team", data={
        "team_name": "TestTeam",
        "password": "securepass"
    })

    assert response.status_code == 200

def test_login_as_admin(test_client, mocker):
    """Test the /login/as_admin route."""
    mock_verify_login = mocker.patch("Service.TeamService.TeamService.verify_login")
    mock_verify_login.return_value.id = 1

    mock_season = mocker.patch("Service.SeasonService.SeasonService.find_latest_season_by_team_id")
    mock_season.return_value.id = 42

    response = test_client.post("/login/as_admin", data={
        "team_name": "TestTeam",
        "password": "securepass"
    })

    assert response.status_code == 200

def test_edit_team(test_client, mocker):
    """Test the /edit_team route."""
    mock_edit_team = mocker.patch("Service.TeamService.TeamService.edit_team")
    mock_edit_team.return_value.id = 1

    response = test_client.post("/edit_team", data={
        "team_id": "1",
        "password": "securepass",
        "club_name": "NewClub",
        "introduction_text": "Updated text"
    })

    assert response.status_code == 200

def test_see_team_as_admin(test_client, mocker):
    """Test the /see_team_as_admin route."""
    response = test_client.post("/see_team_as_admin", data={
        "season_id": "42"
    })

    assert response.status_code == 200

def test_see_team_as_user(test_client, mocker):
    """Test the /see_team_as_user route."""
    mock_get_team_by_name = mocker.patch("Service.TeamService.TeamService.get_team_by_name")
    mock_get_team_by_name.return_value.id = 1

    mock_season = mocker.patch("Service.SeasonService.SeasonService.find_latest_season_by_team_id")
    mock_season.return_value.id = 42

    response = test_client.post("/see_team_as_user", data={
        "team_name": "TestTeam"
    })

    assert response.status_code == 200

def test_see_team_as_user_url(test_client, mocker):
    """Test the /<team_name> route."""
    mock_get_team_by_name = mocker.patch("Service.TeamService.TeamService.get_team_by_name")
    mock_get_team_by_name.return_value.id = 1

    mock_season = mocker.patch("Service.SeasonService.SeasonService.find_latest_season_by_team_id")
    mock_season.return_value.id = 42

    response = test_client.get("/TestTeam")

    assert response.status_code == 200
