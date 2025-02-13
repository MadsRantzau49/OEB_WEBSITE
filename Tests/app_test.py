def test_home_route(test_client):
    """Test the home route."""
    response = test_client.get('/')
    assert response.status_code == 200
    assert b'Hold' in response.data  # Check if 'Essakedøb' is in the response

def test_admin_route(test_client):
    """Test the admin_index route."""
    response = test_client.get('/admin_index')
    assert response.status_code == 200
    assert b'Opret Hold' in response.data  # Simple check to ensure admin page loads
