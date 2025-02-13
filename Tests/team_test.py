def test_create_team(test_client):
    """Test the /create_team route."""
    response = test_client.post("/create_team", data={
        "team_name": "TestTeam",
        "club_name": "TestClub",
        "password": "securepass"
    })
    assert response.status_code == 200
    assert b'Error' not in response.data

def test_create_team_twice(test_client):
    """Test the /create_team route."""
    response = test_client.post("/create_team", data={
        "team_name": "TestTeam",
        "club_name": "TestClub",
        "password": "securepass"
    })
    assert response.status_code == 200
    assert b'Error' in response.data


def test_render_edit_team(test_client):
    """Test the /render/edit_team route."""
    response = test_client.post("/render/edit_team", data={
        "team_name": "TestTeam",
        "password": "securepass"
    })
    assert response.status_code == 200

def test_login_as_admin(test_client):
    """Test the /login/as_min route."""
    response = test_client.post("/login/as_admin", data={
        "team_name": "TestTeam",
        "password": "securepass"
    })
    assert response.status_code == 200

def test_edit_team(test_client):
    """Test the /edit_team route."""
    response = test_client.post("/edit_team", data={
        "team_id": "1",
        "password": "securepass",
        "club_name": "NewClub",
        "introduction_text": "Updated text"
    })
    assert response.status_code == 200

def test_see_team_as_admin(test_client):
    """Test the /see_team_as_admin route."""
    response = test_client.post("/see_team_as_admin", data={
        "season_id": "42"
    })
    assert response.status_code == 200

def test_see_team_as_user(test_client):
    """Test the /see_team_as_user route."""
    response = test_client.post("/see_team_as_user", data={
        "team_name": "TestTeam"
    })
    assert response.status_code == 200

def test_see_team_as_user_url(test_client):
    """Test the /<team_name> route."""
    response = test_client.get("/TestTeam")
    assert response.status_code == 200
